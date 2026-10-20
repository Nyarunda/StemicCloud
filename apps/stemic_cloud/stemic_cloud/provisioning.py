"""Tenant provisioning: reserve the subdomain, create the tenant record, assign a deployment group, then a background
job runs the plan (provisioning_rules.plan): the site and its database, the apps, migrations, the insurance business
type, the organisation's administrator, scheduled jobs, the first backup, nginx, a health check, the administrator's
set-password email, and activation. Each step's command, output and time are kept on the job; a failed job is retried
from the step that failed."""

import secrets

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from stemic_cloud.audit import log
from stemic_cloud.rules import provisioning_rules as P
from stemic_cloud.rules.naming_rules import site_name, subdomain_findings
from stemic_cloud.runner import RunError, check_health, group_for_new_tenant, result_of, run

PLATFORM_ROLES = ("Platform Super Admin", "Platform Support", "System Manager")


def create_tenant(organization, subdomain, admin_email, admin_first_name):
	"""Reserves the subdomain and queues the job; returns the tenant's name (its site)."""
	problems = subdomain_findings(subdomain)
	if problems:
		frappe.throw(_(problems[0]))
	if not P.email_safe(admin_email):
		frappe.throw(_("The administrator's email cannot be used for the ERP: {0}").format(admin_email))
	root = frappe.get_cached_doc("Cloud Settings").root_domain
	site = site_name(subdomain, root)
	if frappe.db.exists("Tenant", site) or frappe.db.exists("Tenant", {"subdomain": subdomain}):
		frappe.throw(_("{0} is taken").format(site))
	group = group_for_new_tenant()
	tenant = frappe.get_doc({"doctype": "Tenant", "site_name": site, "subdomain": subdomain,
		"organization": organization, "deployment_group": group.name, "status": "Reserved", "url": f"https://{site}",
		"admin_email": admin_email, "health": "Unknown"})
	tenant.flags.ignore_permissions = True
	tenant.insert()
	start_job(site)
	return site


def start_job(tenant):
	job = frappe.get_doc({"doctype": "Tenant Provisioning Job", "tenant": tenant, "status": "Queued", "attempts": 0})
	job.insert(ignore_permissions=True)
	frappe.db.set_value("Tenant", tenant, {"last_job": job.name, "status": "Provisioning"})
	log("Provisioning queued", tenant=tenant, organization=frappe.db.get_value("Tenant", tenant, "organization"),
		reference=("Tenant Provisioning Job", job.name))
	frappe.enqueue("stemic_cloud.provisioning.run_job", queue="long", timeout=3 * 3600, job=job.name,
		enqueue_after_commit=True)
	return job.name


def _plan(tenant, group):
	org = frappe.get_doc("Cloud Organization", tenant.organization)
	apps = [a.strip() for a in (group.apps or "").splitlines() if a.strip()]
	first = (frappe.db.get_value("User", tenant.admin_email, "first_name") or "Admin").replace('"', "")
	return P.plan(tenant.site_name, apps, tenant.admin_email, first, org.org_type, tenant.url,
		f"https://{tenant.site_name}/api/method/ping", reload_web=bool(group.setup_nginx))


def run_job(job):
	"""The background job: every step not yet done, in order; stops at the first failure that is not optional."""
	j = frappe.get_doc("Tenant Provisioning Job", job)
	tenant = frappe.get_doc("Tenant", j.tenant)
	group = frappe.get_doc("Deployment Group", tenant.deployment_group)
	steps = _plan(tenant, group)
	done = [s.code for s in j.steps if s.status in ("Done", "Skipped")]
	j.db_set({"status": "Running", "attempts": cint(j.attempts) + 1, "started_on": now_datetime(), "error": None})
	secrets_ = {"admin_password": secrets.token_urlsafe(24)}  # never stored: the administrator sets their own
	for step in P.resume_from(steps, done):
		row = next((r for r in j.steps if r.code == step.code), None) or j.append("steps", {"code": step.code,
			"title": step.title})
		row.update({"status": "Running", "started_on": now_datetime(), "command": "bench " + " ".join(
			P.shown(step.argv)) if step.argv else step.kind, "output": None})
		j.save(ignore_permissions=True)
		frappe.db.commit()
		try:
			output = _do(step, tenant, group, secrets_)
			row.update({"status": "Done", "ended_on": now_datetime(), "output": output})
		except Exception as e:
			row.update({"status": "Skipped" if step.optional else "Failed", "ended_on": now_datetime(),
				"output": str(e)[-8000:]})
			if not step.optional:
				j.status, j.error, j.ended_on = "Failed", f"{step.title}: {str(e)[-500:]}", now_datetime()
				j.save(ignore_permissions=True)
				tenant.db_set("status", "Failed")
				log("Provisioning failed", tenant=tenant.name, organization=tenant.organization,
					reference=("Tenant Provisioning Job", j.name), details={"step": step.code}, actor="Administrator")
				frappe.db.commit()
				_tell_platform(tenant, j)
				return
		j.save(ignore_permissions=True)
		frappe.db.commit()
	j.db_set({"status": "Succeeded", "ended_on": now_datetime()})
	frappe.db.commit()


def _do(step, tenant, group, secrets_):
	if step.kind == "bench":
		output = run(group, step.argv, secrets_)
		if step.code == "backup":
			tenant.db_set("last_backup_on", now_datetime())
		return output
	if step.kind == "http":
		ok, detail = check_health(group, tenant.site_name)
		tenant.db_set({"health": "Healthy" if ok else "Unreachable", "last_health_check": now_datetime()})
		if not ok:
			raise RunError(_("The site does not answer: {0}").format(detail))
		return detail
	if step.code == "activate":
		version = _version(group, tenant.site_name)
		tenant.db_set({"status": "Active", "app_version": version})
		log("Tenant activated", tenant=tenant.name, organization=tenant.organization, actor="Administrator")
		_tell_owner(tenant)
		return "active"
	return "reserved"


def _version(group, site):
	if group.runner == "Dry Run":
		return "dry-run"
	try:
		return str(result_of(run(group, P.app_version(site))) or "")[:40]
	except Exception:
		return None


def _tell_owner(tenant):
	owner = frappe.db.get_value("Cloud Organization", tenant.organization, "owner_user")
	email = owner and frappe.db.get_value("User", owner, "email")
	if email:
		frappe.sendmail(recipients=[email], subject=_("Your Stemic Insurance ERP is ready"), message=_(
			"Your insurance ERP is ready at <a href=\"{0}\">{0}</a>. The administrator, {1}, has an email to set a "
			"password there.").format(tenant.url, tenant.admin_email))


def _tell_platform(tenant, job):
	from frappe.desk.form.assign_to import add

	users = [u for u in frappe.get_all("Has Role", filters={"role": "Platform Support", "parenttype": "User"},
		pluck="parent") if frappe.db.get_value("User", u, "enabled")]
	if users:
		add({"doctype": "Tenant Provisioning Job", "name": job.name, "assign_to": users[:1], "description": _(
			"Provisioning {0} failed: {1}").format(tenant.name, job.error)})


def _require_platform():
	if not set(frappe.get_roles()) & set(PLATFORM_ROLES):
		frappe.throw(_("Platform staff only"), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def retry(job):
	"""Platform support retries a failed job from the failed step."""
	_require_platform()
	j = frappe.get_doc("Tenant Provisioning Job", job)
	if j.status != "Failed":
		frappe.throw(_("Only a failed job is retried"))
	j.db_set("status", "Queued")
	frappe.db.set_value("Tenant", j.tenant, "status", "Provisioning")
	log("Provisioning retried", tenant=j.tenant, reference=("Tenant Provisioning Job", j.name))
	frappe.enqueue("stemic_cloud.provisioning.run_job", queue="long", timeout=3 * 3600, job=j.name,
		enqueue_after_commit=True)


def set_read_only(tenant, on: bool):
	t = frappe.get_doc("Tenant", tenant)
	group = frappe.get_doc("Deployment Group", t.deployment_group)
	for argv in (P.suspend(t.site_name) if on else P.resume(t.site_name)):
		run(group, argv)
	t.db_set({"read_only": 1 if on else 0, "status": "Suspended" if on else "Active"})
	log("Tenant read-only" if on else "Tenant resumed", tenant=t.name, organization=t.organization)


def daily():
	"""Health and usage of each active tenant: it answers, how many ERP users are active against the plan."""
	from stemic_cloud.rules.subscription_rules import seat_findings

	for name in frappe.get_all("Tenant", filters={"status": ["in", ["Active", "Suspended"]]}, pluck="name"):
		try:
			t = frappe.get_doc("Tenant", name)
			group = frappe.get_doc("Deployment Group", t.deployment_group)
			ok, _detail = check_health(group, t.site_name)
			t.db_set({"health": "Healthy" if ok else "Unreachable", "last_health_check": now_datetime()})
			count = result_of(run(group, P.count_users(t.site_name)))
			users = cint(count) if str(count).isdigit() else None
			sub = frappe.db.get_value("Cloud Subscription", {"organization": t.organization, "status": ["!=",
				"Cancelled"]}, ["name", "plan"], as_dict=True)
			if sub and users is not None:
				limit = frappe.db.get_value("Subscription Plan", sub.plan, "max_users")
				warning = seat_findings(cint(limit) or None, users)
				frappe.db.set_value("Cloud Subscription", sub.name, {"active_users": users,
					"usage_checked_on": now_datetime(), "seat_warning": warning[0] if warning else None})
			version = _version(group, t.site_name)
			if version:
				t.db_set("app_version", version)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Stemic Cloud: tenant {name}")

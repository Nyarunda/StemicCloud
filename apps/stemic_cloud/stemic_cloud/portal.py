"""The customer portal (app.{root domain}/cloud): an organisation's own account, subscription, ERP environment, team,
onboarding and security. It shows no insurance data; the ERP is opened on the tenant's own address."""

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime

from stemic_cloud.accounts import membership, my_organizations, require
from stemic_cloud.audit import log
from stemic_cloud.rules.membership_rules import ROLES, can
from stemic_cloud.rules.onboarding_rules import STEPS, checklist, progress

NAV = [("", "Dashboard"), ("erp", "My ERP"), ("billing", "Subscription & Billing"), ("team", "Team"),
	("onboarding", "Onboarding"), ("security", "Security")]


def base(context, key, title):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/cloud" + (f"/{key}" if key else "")
		raise frappe.Redirect
	orgs = my_organizations()
	if not orgs:
		frappe.local.flags.redirect_location = "/register"
		raise frappe.Redirect
	wanted = frappe.form_dict.get("org")
	org = next((o for o in orgs if o.name == wanted), orgs[0])
	doc = frappe.get_doc("Cloud Organization", org.name)
	context.update({"orgs": orgs, "org": doc, "role": org.role,
		"nav": [n for n in NAV if n[0] != "billing" or can(org.role, "view_billing")], "page_key": key, "title": _(title),
		"full_name": frappe.utils.get_fullname(frappe.session.user),
		"support_email": frappe.get_cached_doc("Cloud Settings").support_email,
		"no_cache": 1, "show_sidebar": False, "full_width": 1, "can": lambda action: can(org.role, action),
		"fmt_date": lambda d: frappe.utils.formatdate(d) if d else "",
		"fmt_dt": lambda d: frappe.utils.format_datetime(d, "dd-MM-yyyy HH:mm") if d else "",
		"money": lambda v, c=None: frappe.format(v or 0, {"fieldtype": "Currency", "options": c, "precision": 2},
			currency=c)})
	return doc


def _tenant(org):
	name = frappe.db.get_value("Tenant", {"organization": org, "status": ["!=", "Archived"]}, "name",
		order_by="creation desc")
	return frappe.get_doc("Tenant", name) if name else None


def _subscription(org):
	name = frappe.db.get_value("Cloud Subscription", {"organization": org}, "name", order_by="creation desc")
	return frappe.get_doc("Cloud Subscription", name) if name else None


def dashboard(context):
	org = base(context, "", "Dashboard")
	sub, tenant = _subscription(org.name), _tenant(org.name)
	plan = frappe.get_cached_doc("Subscription Plan", sub.plan) if sub else None
	unpaid = frappe.get_all("Subscription Invoice", filters={"organization": org.name, "status": "Issued"},
		fields=["name", "amount", "currency", "due_date"], order_by="due_date")
	admins = frappe.db.count("Organization Member", {"organization": org.name, "status": "Active",
		"role": ["in", ["Owner", "Admin"]]})
	context.update({"sub": sub, "plan": plan, "tenant": tenant, "unpaid": unpaid, "admins": admins,
		"members": frappe.db.count("Organization Member", {"organization": org.name, "status": "Active"}),
		"activity": frappe.get_all("Cloud Audit Log", filters={"organization": org.name}, fields=["at", "action",
			"actor"], order_by="at desc", limit=10),
		"job": frappe.get_doc("Tenant Provisioning Job", tenant.last_job) if tenant and tenant.last_job else None,
		"progress": progress({s.code for s in org.onboarding if s.done})})


def erp(context):
	org = base(context, "erp", "My ERP")
	tenant = _tenant(org.name)
	context.update({"tenant": tenant, "job": frappe.get_doc("Tenant Provisioning Job", tenant.last_job)
		if tenant and tenant.last_job else None})


def billing(context):
	org = base(context, "billing", "Subscription & Billing")
	require(org.name, "view_billing")
	sub = _subscription(org.name)
	context.update({"sub": sub, "plan": frappe.get_cached_doc("Subscription Plan", sub.plan) if sub else None,
		"plans": frappe.get_all("Subscription Plan", filters={"enabled": 1, "is_public": 1}, fields=["name",
			"plan_name", "monthly_price", "annual_price", "currency", "max_users", "contact_sales", "description"],
			order_by="sort_order asc, monthly_price asc"),
		"invoices": frappe.get_all("Subscription Invoice", filters={"organization": org.name}, fields=["name",
			"period_start", "period_end", "amount", "currency", "due_date", "status", "paid_on", "payment_reference"],
			order_by="period_start desc", limit=50)})


def team(context):
	org = base(context, "team", "Team")
	context.update({"members": frappe.db.sql("""select m.name, m.user, m.role, m.joined_on, u.full_name, u.last_login
			from `tabOrganization Member` m join `tabUser` u on u.name = m.user
			where m.organization = %s and m.status = 'Active' order by field(m.role, 'Owner', 'Admin', 'Billing Admin',
			'Member'), u.full_name""", org.name, as_dict=True),
		"invitations": frappe.get_all("Organization Invitation", filters={"organization": org.name,
			"status": "Pending"}, fields=["name", "email", "role", "expires_on", "invited_by"]), "roles": ROLES})


def onboarding(context):
	org = base(context, "onboarding", "Onboarding")
	tenant = _tenant(org.name)
	done = {s.code for s in org.onboarding if s.done}
	context.update({"tenant": tenant, "steps": checklist(done, tenant.url if tenant else ""),
		"progress": progress(done)})


def security(context):
	org = base(context, "security", "Security")
	user = frappe.session.user
	context.update({
		"logins": frappe.get_all("Activity Log", filters={"user": user, "operation": ["in", ["Login", "Logout"]]},
			fields=["creation", "operation", "status", "ip_address"], order_by="creation desc", limit=20),
		"sessions": frappe.db.count("Sessions", {"user": user}) if frappe.db.table_exists("Sessions") else None,
		"two_factor": bool(frappe.db.get_single_value("System Settings", "enable_two_factor_auth")),
		"grants": frappe.get_all("Tenant Access Grant", filters={"organization": org.name}, fields=["name",
			"requested_by", "reason", "scope", "hours", "status", "valid_until", "creation"], order_by="creation desc",
			limit=20)})


def invitation(context):
	from stemic_cloud.accounts import accept

	token = frappe.form_dict.get("token")
	try:
		target = accept(token)
	except frappe.Redirect:
		raise
	except Exception as e:
		frappe.db.rollback()
		context.update({"error": frappe.utils.strip_html(str(e)), "title": _("Invitation")})
		return
	frappe.db.commit()  # a GET is not committed by Frappe: the account, membership and acceptance would be lost
	frappe.local.flags.redirect_location = target
	raise frappe.Redirect


# ---- actions


@frappe.whitelist(methods=["POST"])
def mark_step(organization, code, done=1):
	require(organization, "onboarding")
	org = frappe.get_doc("Cloud Organization", organization)
	title = next((t for c, t, _p in STEPS if c == code), None)
	if not title:
		frappe.throw(_("No such step"))
	row = next((s for s in org.onboarding if s.code == code), None)
	if not row:
		row = org.append("onboarding", {"code": code, "title": title})
	row.update({"done": cint(done), "done_by": frappe.session.user if cint(done) else None,
		"done_on": now_datetime() if cint(done) else None})
	org.onboarding_progress = progress({s.code for s in org.onboarding if s.done})
	org.flags.ignore_permissions = True
	org.save()
	return org.onboarding_progress


@frappe.whitelist(methods=["POST"])
def request_export(organization, note=None):
	"""Asks support for a full export of the tenant's data (phase 1: support prepares it by hand)."""
	require(organization, "request_export")
	support = frappe.get_cached_doc("Cloud Settings").support_email
	tenant = _tenant(organization)
	if support:
		frappe.sendmail(recipients=[support], subject=_("Data export requested: {0}").format(organization),
			message=_("{0} asks for a data export of {1}. {2}").format(frappe.session.user,
			tenant.name if tenant else "-", frappe.utils.escape_html(note or "")))
	log("Data export requested", organization=organization, tenant=tenant.name if tenant else None,
		details={"note": note})
	return _("Support was asked to prepare the export; you will hear from us by email.")


@frappe.whitelist(methods=["POST"])
def decide_access(organization, grant, approve):
	from stemic_cloud.admin import decide_access as decide

	m = require(organization, "approve_access")
	if frappe.db.get_value("Tenant Access Grant", grant, "organization") != organization:
		frappe.throw(_("Not your organisation's request"), frappe.PermissionError)
	decide(grant, approve, m.role)


@frappe.whitelist(methods=["POST"])
def end_access(organization, grant):
	from stemic_cloud.admin import end_access as end

	require(organization, "approve_access")
	if frappe.db.get_value("Tenant Access Grant", grant, ["organization", "status"]) != (organization, "Approved"):
		frappe.throw(_("Only an approved access of your organisation is ended"))
	end(grant, "Revoked")


@frappe.whitelist(methods=["POST"])
def sign_out_elsewhere():
	"""Ends the person's other sessions (keeps this one)."""
	from frappe.sessions import clear_sessions

	clear_sessions(user=frappe.session.user, keep_current=True, force=True)
	log("Signed out elsewhere", details={"user": frappe.session.user})


__all__ = ["membership", "getdate"]

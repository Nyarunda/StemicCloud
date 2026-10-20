"""Platform administration helpers: the revenue card, platform-staff access to a tenant (asked, approved by the
organisation, time-limited) and revoking a person's sessions."""

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime

from stemic_cloud.audit import log
from stemic_cloud.rules import access_rules as A
from stemic_cloud.rules import provisioning_rules as P
from stemic_cloud.rules.subscription_rules import invoice_amount

PLATFORM = ("Platform Super Admin", "Platform Support", "Platform Finance", "System Manager")
SCOPE_ROLES = {"Read Only": ["Report Manager"], "Support (Read and Write)": ["System Manager"]}


def _platform():
	if not set(frappe.get_roles()) & set(PLATFORM):
		frappe.throw(_("Platform staff only"), frappe.PermissionError)


@frappe.whitelist()
def mrr_card():
	"""Monthly recurring revenue of active and past-due subscriptions, per currency (the card shows the first)."""
	_platform()
	totals = {}
	for s in frappe.db.sql("""select s.billing_cycle, p.monthly_price, p.annual_price, p.currency
			from `tabCloud Subscription` s join `tabSubscription Plan` p on p.name = s.plan
			where s.status in ('Active', 'Past Due', 'Grace')""", as_dict=True):
		amount = invoice_amount(s.monthly_price, s.annual_price, s.billing_cycle)
		monthly = amount / 12 if s.billing_cycle == "Annual" else amount
		totals[s.currency] = totals.get(s.currency, 0) + float(monthly)
	currency, value = (next(iter(totals.items())) if totals else ("USD", 0))
	return {"value": round(value, 2), "fieldtype": "Currency", "currency": currency}


# ---- access to a tenant


@frappe.whitelist(methods=["POST"])
def request_access(tenant, reason, scope="Read Only", hours=4):
	"""Platform staff ask; the Tenant Access Grant controller checks, notifies the approvers and logs."""
	_platform()
	g = frappe.get_doc({"doctype": "Tenant Access Grant", "tenant": tenant, "reason": reason, "scope": scope,
		"hours": cint(hours)})
	g.insert(ignore_permissions=True)
	return g.name


def tell_approvers(org, grant):
	users = frappe.get_all("Organization Member", filters={"organization": org, "status": "Active",
		"role": ["in", ["Owner", "Admin"]]}, pluck="user")
	emails = [e for e in (frappe.db.get_value("User", u, "email") for u in users) if e]
	portal = frappe.get_cached_doc("Cloud Settings").portal_url.rstrip("/")
	if emails:
		frappe.sendmail(recipients=emails, subject=_("Stemic support asks to access your ERP"), message=_(
			"{0} asks for {1} access to your ERP for {2} hours: {3}<br>Approve or reject it at {4}/cloud/security"
		).format(grant.requested_by, _(grant.scope), grant.hours, frappe.utils.escape_html(grant.reason), portal))


def decide_access(grant, approve, member_role):
	"""The organisation's owner or admin decides (accounts.require checked the role); approval creates a login on
	the tenant for the requester with the scope's roles, ended when the time is up."""
	from stemic_cloud.rules.membership_rules import can
	from stemic_cloud.runner import run

	g = frappe.get_doc("Tenant Access Grant", grant)
	if not can(member_role, "approve_access"):
		frappe.throw(_("Only an owner or admin decides"), frappe.PermissionError)
	if g.status != "Requested":
		frappe.throw(_("This request is {0}").format(_(g.status)))
	if not cint(approve):
		g.db_set({"status": "Rejected", "decided_by": frappe.session.user})
		log("Access rejected", organization=g.organization, tenant=g.tenant, reference=("Tenant Access Grant", g.name))
		return
	t = frappe.get_doc("Tenant", g.tenant)
	group = frappe.get_doc("Deployment Group", t.deployment_group)
	local, _sep, domain = (frappe.db.get_value("User", g.requested_by, "email") or "").partition("@")
	login = f"{local}+{g.name.lower()}@{domain}"
	if not P.email_safe(login):
		frappe.throw(_("The requester's address cannot be used on the tenant"))
	run(group, P.grant_user(t.site_name, login, "Stemic Support", SCOPE_ROLES.get(g.scope, ["Report Manager"])))
	now = now_datetime()
	g.db_set({"status": "Approved", "decided_by": frappe.session.user, "valid_from": now,
		"valid_until": add_to_date(now, hours=cint(g.hours)), "tenant_user": login})
	log("Access approved", organization=g.organization, tenant=g.tenant, reference=("Tenant Access Grant", g.name),
		details={"login": login, "until": str(g.valid_until)})


def end_access(grant, status="Expired"):
	from stemic_cloud.runner import run

	g = frappe.get_doc("Tenant Access Grant", grant)
	if g.tenant_user:
		t = frappe.get_doc("Tenant", g.tenant)
		run(frappe.get_doc("Deployment Group", t.deployment_group), P.revoke_user(t.site_name, g.tenant_user))
	g.db_set("status", status)
	log(f"Access {status.lower()}", organization=g.organization, tenant=g.tenant,
		reference=("Tenant Access Grant", g.name), actor=frappe.session.user)


def hourly():
	"""Grants whose time is up are ended and their tenant login disabled."""
	now = now_datetime()
	for g in frappe.get_all("Tenant Access Grant", filters={"status": "Approved"}, fields=["name", "status",
			"valid_until"]):
		if A.expired(g.status, g.valid_until, now):
			try:
				end_access(g.name)
				frappe.db.commit()
			except Exception:
				frappe.db.rollback()
				frappe.log_error(title=f"Stemic Cloud: ending access {g.name}")


@frappe.whitelist(methods=["POST"])
def revoke_sessions(user):
	"""Platform Super Admin: logs a person out everywhere (a lost device, a leaving employee)."""
	if not set(frappe.get_roles()) & {"Platform Super Admin", "System Manager"}:
		frappe.throw(_("Platform Super Admin only"), frappe.PermissionError)
	from frappe.sessions import clear_sessions

	clear_sessions(user=user, keep_current=user == frappe.session.user, force=True)
	log("Sessions revoked", details={"user": user})


@frappe.whitelist(methods=["POST"])
def end_my_access(grant):
	"""The requester (or a Platform Super Admin) ends an approved access before its time."""
	_platform()
	g = frappe.db.get_value("Tenant Access Grant", grant, ["status", "requested_by"], as_dict=True)
	if not g or g.status != "Approved":
		frappe.throw(_("Only an approved access is ended"))
	if g.requested_by != frappe.session.user and "Platform Super Admin" not in frappe.get_roles():
		frappe.throw(_("Only the requester or a Platform Super Admin ends it"), frappe.PermissionError)
	end_access(grant, "Revoked")

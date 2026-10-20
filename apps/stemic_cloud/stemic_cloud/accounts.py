"""Registration, email verification and teams.

Register stores the form as a Cloud Registration and emails a link; the link proves the address, and only then are
the user, the organisation (its owner a member with role Owner), the trial subscription and the tenant made, and the
provisioning job queued. The person then sets a password on Frappe's own page. Logins, password reset, two-factor
codes, lockout after failed attempts and sessions are Frappe's; the portal adds the organisation roles."""

import datetime
import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_to_date, cint, now_datetime, validate_email_address

from stemic_cloud.audit import log
from stemic_cloud.rules.membership_rules import OWNER, ROLES, can, invitation_findings, role_change_findings, token_hash
from stemic_cloud.rules.naming_rules import subdomain_findings

CUSTOMER_ROLE = "Cloud Customer"


def _key():
	from frappe.utils.password import get_encryption_key

	return get_encryption_key()


def settings():
	return frappe.get_cached_doc("Cloud Settings")


# ---- who may do what


def desk_user():
	"""The Stemic Cloud desk app is for platform staff; customers have only the portal."""
	return frappe.session.user != "Guest" and frappe.get_cached_value("User", frappe.session.user,
		"user_type") == "System User"


def membership(organization, user=None):
	return frappe.db.get_value("Organization Member", {"organization": organization, "user": user or
		frappe.session.user, "status": "Active"}, ["name", "role"], as_dict=True)


def require(organization, action):
	"""The person's role in the organisation allows the action (platform staff are not members and get nothing)."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Log in first"), frappe.PermissionError)
	m = membership(organization)
	if not m or not can(m.role, action):
		frappe.throw(_("Your role in this organisation does not allow that"), frappe.PermissionError)
	return m


def my_organizations(user=None):
	return frappe.db.sql("""select o.name, o.org_name, m.role from `tabOrganization Member` m
		join `tabCloud Organization` o on o.name = m.organization
		where m.user = %s and m.status = 'Active' order by o.org_name""", user or frappe.session.user, as_dict=True)


def subdomain_taken(subdomain):
	return bool(frappe.db.exists("Tenant", {"subdomain": subdomain}) or frappe.db.exists("Cloud Organization",
		{"preferred_subdomain": subdomain}) or frappe.db.exists("Cloud Registration", {"subdomain": subdomain,
		"status": "Pending", "expires_on": [">", now_datetime()]}))


@frappe.whitelist(allow_guest=True)
def check_subdomain(subdomain):
	problems = subdomain_findings(subdomain)
	if not problems and subdomain_taken((subdomain or "").strip().lower()):
		problems = [_("That address is taken")]
	return {"ok": not problems, "problems": problems}


# ---- registration


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60 * 60)
def register(full_name, email, org_name, org_type, subdomain, plan, billing_cycle="Monthly", phone=None,
		registration_number=None, country="Kenya", currency="KES", time_zone="Africa/Nairobi", accept_terms=0):
	"""The registration form: checked, stored, and a verification link emailed. The same answer whether or not the
	address is known, so the form cannot be used to find who has an account."""
	email = (validate_email_address(email or "", throw=True) or "").strip().lower()
	subdomain = (subdomain or "").strip().lower()
	problems = subdomain_findings(subdomain)
	if not problems and subdomain_taken(subdomain):
		problems.append(_("That address is taken"))
	if not (full_name or "").strip() or not (org_name or "").strip():
		problems.append(_("Give your name and the company's name"))
	p = frappe.db.get_value("Subscription Plan", plan, ["enabled", "is_public", "contact_sales"], as_dict=True)
	if not p or not p.enabled or not p.is_public:
		problems.append(_("Choose a plan"))
	elif p.contact_sales:
		problems.append(_("This plan is arranged with our sales team; write to us"))
	if billing_cycle not in ("Monthly", "Annual"):
		problems.append(_("Choose monthly or annual billing"))
	if not cint(accept_terms):
		problems.append(_("Accept the terms of service"))
	if problems:
		frappe.throw("<br>".join(problems), title=_("Registration"))
	message = {"message": _("We have sent a link to {0}. Open it within {1} hours to create your organisation.").format(
		email, settings().verification_hours or 48)}
	if frappe.db.exists("User", email):  # an existing account: tell them by email, not on the page
		_mail(email, _("Your Stemic Insurance registration"), _("Someone (perhaps you) tried to register a new "
			"organisation with this address, which already has an account. Log in at {0} instead.").format(
			settings().portal_url))
		return message
	token = secrets.token_urlsafe(32)
	reg = frappe.get_doc({"doctype": "Cloud Registration", "email": email, "full_name": full_name.strip(),
		"org_name": org_name.strip(), "org_type": org_type, "registration_number": registration_number,
		"country": country, "currency": currency, "time_zone": time_zone, "phone": phone, "subdomain": subdomain,
		"plan": plan, "billing_cycle": billing_cycle, "terms_version": settings().terms_version,
		"ip_address": getattr(frappe.local, "request_ip", None), "token_hash": token_hash(token, _key()),
		"expires_on": add_to_date(now_datetime(), hours=cint(settings().verification_hours or 48)),
		"status": "Pending"}).insert(ignore_permissions=True)
	link = f"{settings().portal_url.rstrip('/')}/register/verify?token={token}"
	_mail(email, _("Confirm your email for Stemic Insurance"), _("Hello {0},<br><br>Confirm your email to create {1} on "
		"Stemic Insurance:<br><a href=\"{2}\">{2}</a><br><br>The link works once, for {3} hours.").format(
		frappe.utils.escape_html(full_name), frappe.utils.escape_html(org_name), link,
		settings().verification_hours or 48))
	log("Registration started", reference=("Cloud Registration", reg.name), details={"email": email,
		"subdomain": subdomain}, actor="Guest")
	return message


def _mail(to, subject, message):
	frappe.sendmail(recipients=[to], subject=subject, message=message, now=True)


def verify(token):
	"""The verification link: creates everything and returns the link to set a password."""
	from stemic_cloud.provisioning import create_tenant
	from stemic_cloud.subscriptions import start_subscription

	reg_name = frappe.db.get_value("Cloud Registration", {"token_hash": token_hash(token or "", _key())}, "name")
	if not reg_name:
		frappe.throw(_("This link is not valid"), frappe.PermissionError)
	reg = frappe.get_doc("Cloud Registration", reg_name)
	if reg.status != "Pending":
		frappe.throw(_("This link was already used; log in instead"))
	if now_datetime() > reg.expires_on:
		reg.db_set("status", "Expired")
		frappe.throw(_("This link has expired; register again"))
	if subdomain_taken_by_other(reg):
		frappe.throw(_("The address {0} was taken meanwhile; register again with another").format(reg.subdomain))
	first, _sp, last = reg.full_name.partition(" ")
	user = frappe.db.exists("User", reg.email) or frappe.get_doc({"doctype": "User", "email": reg.email,
		"first_name": first, "last_name": last or None, "user_type": "Website User", "send_welcome_email": 0,
		"roles": [{"role": CUSTOMER_ROLE}]}).insert(ignore_permissions=True).name
	if CUSTOMER_ROLE not in frappe.get_roles(user):
		frappe.get_doc("User", user).add_roles(CUSTOMER_ROLE)
	org = frappe.get_doc({"doctype": "Cloud Organization", "org_name": reg.org_name, "org_type": reg.org_type,
		"registration_number": reg.registration_number, "country": reg.country, "currency": reg.currency,
		"time_zone": reg.time_zone, "business_email": reg.email, "phone": reg.phone,
		"preferred_subdomain": reg.subdomain, "status": "Active", "owner_user": user, "terms_version": reg.terms_version,
		"terms_accepted_on": reg.creation, "terms_ip": reg.ip_address}).insert(ignore_permissions=True)
	frappe.get_doc({"doctype": "Organization Member", "organization": org.name, "user": user, "role": OWNER,
		"status": "Active", "added_by": user, "joined_on": now_datetime()}).insert(ignore_permissions=True)
	start_subscription(org.name, reg.plan, reg.billing_cycle)
	tenant = create_tenant(org.name, reg.subdomain, reg.email, first)
	reg.db_set({"status": "Verified", "organization": org.name, "token_hash": None})
	log("Organization registered", organization=org.name, tenant=tenant, actor=user,
		reference=("Cloud Organization", org.name))
	frappe.cache.hset("redirect_after_login", user, "/cloud")
	return frappe.get_doc("User", user)._reset_password()


def subdomain_taken_by_other(reg):
	return bool(frappe.db.exists("Tenant", {"subdomain": reg.subdomain}) or frappe.db.exists("Cloud Organization",
		{"preferred_subdomain": reg.subdomain}))


# ---- team


@frappe.whitelist(methods=["POST"])
def invite(organization, email, role):
	m = require(organization, "manage_team")
	email = (validate_email_address(email or "", throw=True) or "").strip().lower()
	if role not in ROLES:
		frappe.throw(_("Choose a role"))
	if role == OWNER and m.role != OWNER:
		frappe.throw(_("Only an owner invites an owner"))
	existing = frappe.db.get_value("User", email, "name")
	if existing and membership(organization, existing):
		frappe.throw(_("{0} is already a member").format(email))
	token = secrets.token_urlsafe(32)
	inv = frappe.get_doc({"doctype": "Organization Invitation", "organization": organization, "email": email,
		"role": role, "status": "Pending", "invited_by": frappe.session.user, "token_hash": token_hash(token, _key()),
		"expires_on": add_to_date(now_datetime(), days=cint(settings().invitation_days or 7))}).insert(
		ignore_permissions=True)
	org_name = frappe.db.get_value("Cloud Organization", organization, "org_name")
	link = f"{settings().portal_url.rstrip('/')}/cloud/invitation?token={token}"
	_mail(email, _("You are invited to {0} on Stemic Insurance").format(org_name), _("{0} invited you to {1} as {2}."
		"<br><a href=\"{3}\">{3}</a>").format(frappe.utils.escape_html(frappe.utils.get_fullname()),
		frappe.utils.escape_html(org_name), _(role), link))
	log("Member invited", organization=organization, reference=("Organization Invitation", inv.name),
		details={"email": email, "role": role})
	return inv.name


@frappe.whitelist(methods=["POST"])
def revoke_invitation(invitation):
	inv = frappe.get_doc("Organization Invitation", invitation)
	require(inv.organization, "manage_team")
	if inv.status == "Pending":
		inv.db_set("status", "Revoked")
		log("Invitation revoked", organization=inv.organization, reference=("Organization Invitation", inv.name))


def invitation_of(token):
	name = frappe.db.get_value("Organization Invitation", {"token_hash": token_hash(token or "", _key())}, "name")
	if not name:
		frappe.throw(_("This invitation link is not valid"), frappe.PermissionError)
	return frappe.get_doc("Organization Invitation", name)


def accept(token):
	"""Accepting: a person without an account gets one (and sets a password); a logged-in person must be the one
	invited. Returns where to go next."""
	inv = invitation_of(token)
	now = now_datetime()
	user = frappe.session.user
	if user == "Guest":
		if frappe.db.exists("User", inv.email):
			return "/login?redirect-to=" + frappe.utils.quote(f"/cloud/invitation?token={token}")
		u = frappe.get_doc({"doctype": "User", "email": inv.email, "first_name": inv.email.split("@")[0],
			"user_type": "Website User", "send_welcome_email": 0, "roles": [{"role": CUSTOMER_ROLE}]}).insert(
			ignore_permissions=True)
		user = u.name
	problems = invitation_findings(inv.status, inv.expires_on, now, inv.email, frappe.db.get_value("User", user,
		"email"))
	if problems:
		if inv.status == "Pending" and now > inv.expires_on:
			inv.db_set("status", "Expired")
		frappe.throw(_(problems[0]))
	if not frappe.db.exists("Has Role", {"parent": user, "role": CUSTOMER_ROLE}):
		frappe.get_doc("User", user).add_roles(CUSTOMER_ROLE)
	old = frappe.db.get_value("Organization Member", {"organization": inv.organization, "user": user}, "name")
	if old:
		frappe.db.set_value("Organization Member", old, {"status": "Active", "role": inv.role})
	else:
		frappe.get_doc({"doctype": "Organization Member", "organization": inv.organization, "user": user,
			"role": inv.role, "status": "Active", "added_by": inv.invited_by, "joined_on": now}).insert(
			ignore_permissions=True)
	inv.db_set({"status": "Accepted", "accepted_by": user, "token_hash": None})
	log("Invitation accepted", organization=inv.organization, actor=user,
		reference=("Organization Invitation", inv.name))
	if frappe.session.user == "Guest":
		frappe.cache.hset("redirect_after_login", user, "/cloud")
		return frappe.get_doc("User", user)._reset_password()
	return "/cloud"


@frappe.whitelist(methods=["POST"])
def change_member(member, role=None, remove=0):
	"""Changes a member's role, or removes the member (remove=1)."""
	row = frappe.get_doc("Organization Member", member)
	actor = require(row.organization, "manage_team")
	owners = frappe.db.count("Organization Member", {"organization": row.organization, "role": OWNER,
		"status": "Active"})
	new_role = None if cint(remove) else role
	problems = role_change_findings(actor.role, row.role, new_role, owners)
	if problems:
		frappe.throw("<br>".join(_(p) for p in problems))
	if new_role is None:
		row.db_set("status", "Removed")
		log("Member removed", organization=row.organization, reference=("Organization Member", row.name),
			details={"user": row.user})
	else:
		row.db_set("role", new_role)
		log("Member role changed", organization=row.organization, reference=("Organization Member", row.name),
			details={"user": row.user, "role": new_role})


__all__ = ["datetime"]

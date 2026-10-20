"""Setting up the control-plane site: the platform roles, the customers' role, login security defaults, three sample
plans and a Dry Run deployment group, so the portal can be tried before a bench is wired in. Re-run on every migrate;
it only adds what is missing and never overwrites what an administrator changed."""

import frappe

PLATFORM_ROLES = ("Platform Super Admin", "Platform Support", "Platform Finance")
CUSTOMER_ROLE = "Cloud Customer"

# Lockout and password strength are Frappe's (System Settings); set once at install where still at Frappe's default.
SECURITY = {"enable_password_policy": 1, "minimum_password_score": 3, "allow_consecutive_login_attempts": 5,
	"allow_login_after_fail": 600, "password_reset_limit": 3}

PLANS = [  # code, name, monthly (USD), users, contact sales, features
	("STARTER", "Starter", 99, 5, 0, [("Policies, quotations and renewals", "Yes"), ("Commissions", "Yes"),
		("Agent portal", "No"), ("Daily backups", "Yes"), ("Support", "Email")]),
	("BUSINESS", "Business", 249, 20, 0, [("Policies, quotations and renewals", "Yes"), ("Commissions", "Yes"),
		("Agent portal", "Yes"), ("Claims and reinsurance", "Yes"), ("Daily backups", "Yes"),
		("Support", "Email and phone")]),
	("ENTERPRISE", "Enterprise", 0, 0, 1, [("Everything in Business", "Yes"), ("Own server", "Optional"),
		("Integrations (IPRS, DMVIC, core banking)", "Yes"), ("Support", "Dedicated")]),
]


def after_install():
	security()  # once: an administrator may loosen it later
	after_migrate()


def after_migrate():
	roles()
	plans()
	deployment_group()
	frappe.db.commit()


def roles():
	for role in PLATFORM_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1, "two_factor_auth": 1}).insert(
				ignore_permissions=True)
	if not frappe.db.exists("Role", CUSTOMER_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": CUSTOMER_ROLE, "desk_access": 0}).insert(
			ignore_permissions=True)


def security():
	s = frappe.get_single("System Settings")
	meta = s.meta
	changed = False
	for field, value in SECURITY.items():
		df = meta.get_field(field)
		if df and str(s.get(field) or "") in ("", str(df.default or ""), "0"):
			s.set(field, value)
			changed = True
	if changed:
		s.flags.ignore_permissions = True
		s.flags.ignore_mandatory = True  # a new site has no language or time zone until its setup wizard
		s.save()


def plans():
	if frappe.db.count("Subscription Plan"):
		return
	for i, (code, name, price, users, sales, features) in enumerate(PLANS):
		frappe.get_doc({"doctype": "Subscription Plan", "plan_code": code, "plan_name": name, "enabled": 1,
			"is_public": 1, "sort_order": i + 1, "currency": "USD", "monthly_price": price,
			"annual_price": price * 10 if price else 0, "max_users": users or None, "contact_sales": sales,
			"features": [{"feature": f, "value": v} for f, v in features]}).insert(ignore_permissions=True)


def deployment_group():
	if frappe.db.count("Deployment Group"):
		return
	frappe.get_doc({"doctype": "Deployment Group", "group_name": "Dry Run", "is_default": 1, "enabled": 1,
		"runner": "Dry Run", "apps": "erpnext\ninsurance", "setup_nginx": 0}).insert(ignore_permissions=True)

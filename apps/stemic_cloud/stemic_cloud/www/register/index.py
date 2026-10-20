"""The registration page (app.{root domain}/register): plans, the company and its ERP address."""

import frappe
from frappe import _

no_cache = 1

ORG_TYPES = ["Insurance Broker", "Insurance Agency", "Insurer / Underwriter", "Managing General Agent",
	"Insurance Service Provider"]


def get_context(context):
	if frappe.session.user != "Guest" and frappe.db.exists("Organization Member", {"user": frappe.session.user,
			"status": "Active"}):
		frappe.local.flags.redirect_location = "/cloud"
		raise frappe.Redirect
	s = frappe.get_cached_doc("Cloud Settings")
	plans = frappe.get_all("Subscription Plan", filters={"enabled": 1, "is_public": 1}, fields=["name", "plan_name",
		"monthly_price", "annual_price", "currency", "max_users", "contact_sales", "description", "trial_days"],
		order_by="sort_order asc, monthly_price asc")
	for p in plans:
		p.features = frappe.get_all("Plan Feature", filters={"parent": p.name, "parenttype": "Subscription Plan"},
			fields=["feature", "value"], order_by="idx")
		p.trial = p.trial_days or s.trial_days
	context.update({"title": _("Start your Stemic Insurance ERP"), "plans": plans, "org_types": ORG_TYPES,
		"root_domain": s.root_domain, "terms_url": s.terms_url, "support_email": s.support_email,
		"wanted": frappe.form_dict.get("plan"), "no_cache": 1, "show_sidebar": False, "full_width": 1,
		"money": lambda v, c=None: frappe.format(v or 0, {"fieldtype": "Currency", "options": c, "precision": 0},
			currency=c)})
	return context

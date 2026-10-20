"""The email verification link: creates the organisation, its subscription and its ERP, then sends the person to set
a password (stemic_cloud.accounts.verify)."""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	from stemic_cloud.accounts import verify

	from stemic_cloud.ornament import rosette

	context.update({"title": _("Confirm your email"), "rosette": rosette(200), "no_cache": 1, "show_sidebar": False})
	try:
		link = verify(frappe.form_dict.get("token"))
	except frappe.Redirect:
		raise
	except Exception as e:
		frappe.db.rollback()
		context.error = frappe.utils.strip_html(str(e)) or _("This link is not valid")
		return context
	frappe.db.commit()
	frappe.local.flags.redirect_location = link
	raise frappe.Redirect

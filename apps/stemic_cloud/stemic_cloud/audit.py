"""The platform's audit trail: one Cloud Audit Log row per administrative or customer action, never changed."""

import json

import frappe
from frappe.utils import now_datetime


def log(action, organization=None, tenant=None, reference=None, details=None, actor=None):
	"""Records an action; reference is (doctype, name). Never raises into the action it records."""
	try:
		frappe.get_doc({"doctype": "Cloud Audit Log", "at": now_datetime(), "actor": actor or frappe.session.user,
			"action": action, "organization": organization, "tenant": tenant,
			"reference_doctype": reference[0] if reference else None,
			"reference_name": reference[1] if reference else None,
			"ip_address": getattr(frappe.local, "request_ip", None),
			"details": details if isinstance(details, str) or details is None else json.dumps(details, default=str)
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title=f"Stemic Cloud: audit {action}")

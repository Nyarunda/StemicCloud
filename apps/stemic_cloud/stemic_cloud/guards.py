"""Fields only the platform's own code sets (status, who decided, the tenant's state). Read-only on the form is not
enough: an API call could still send them, so a save from outside the code that owns them is refused."""

import frappe
from frappe import _


def keep(doc, fields):
	"""Refuses a change to `fields` on a saved document (the owning code writes them with db_set)."""
	if doc.is_new() or doc.flags.ignore_guard:
		return
	before = doc.get_doc_before_save()
	if not before:
		return
	changed = [doc.meta.get_label(f) for f in fields if (doc.get(f) or None) != (before.get(f) or None)]
	if changed:
		frappe.throw(_("{0} is set by the platform, not by editing: {1}").format(_(doc.doctype), ", ".join(changed)))

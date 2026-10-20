# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CloudAuditLog(Document):
	"""What was done on the platform, by whom, from where: append-only."""

	def validate(self):
		if not self.is_new():
			frappe.throw(_("The audit log is never changed"))

	def on_trash(self):
		frappe.throw(_("The audit log is never deleted"))

# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from stemic_cloud.guards import keep


class SubscriptionInvoice(Document):
	"""One period of a subscription billed; paid or voided only through stemic_cloud.subscriptions (with the
	reference or the reason, in the audit log)."""

	def validate(self):
		keep(self, ("subscription", "amount", "status", "paid_on", "payment_reference", "recorded_by", "period_start",
			"period_end"))

	def on_trash(self):
		frappe.throw(_("An invoice is voided, never deleted"))

# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from stemic_cloud.guards import keep


class CloudSubscription(Document):
	"""An organisation's plan, cycle and standing; the status moves only through stemic_cloud.subscriptions."""

	def validate(self):
		keep(self, ("organization", "status", "current_period_start", "current_period_end", "suspended_by",
			"suspended_on", "cancelled_on"))

	def on_trash(self):
		if frappe.db.exists("Subscription Invoice", {"subscription": self.name}):
			frappe.throw(_("A billed subscription is kept"))

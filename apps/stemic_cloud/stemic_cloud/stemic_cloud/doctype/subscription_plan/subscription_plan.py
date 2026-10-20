# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


class SubscriptionPlan(Document):
	"""A plan customers subscribe to: price per month or year, user limit and the features shown on the plans page."""

	def validate(self):
		if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,30}", self.plan_code or ""):
			frappe.throw(_("The code is capitals, digits and dashes"))
		if not self.contact_sales and not (self.monthly_price or 0) > 0:
			frappe.throw(_("A self-service plan has a monthly price"))
		if (self.annual_price or 0) < 0 or (self.max_users or 0) < 0 or (self.trial_days or 0) < 0:
			frappe.throw(_("Prices, users and trial days are not negative"))
		before = self.get_doc_before_save()
		if before and before.currency != self.currency and frappe.db.exists("Cloud Subscription", {"plan": self.name}):
			frappe.throw(_("Subscriptions use this plan; make a new plan for another currency"))

	def on_trash(self):
		if frappe.db.exists("Cloud Subscription", {"plan": self.name}):
			frappe.throw(_("Subscriptions use this plan; take it off the plans page instead"))

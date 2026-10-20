# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from stemic_cloud.guards import keep
from stemic_cloud.rules.access_rules import grant_findings

DECIDED = ("tenant", "scope", "hours", "status", "requested_by", "decided_by", "valid_from", "valid_until",
	"tenant_user")


class TenantAccessGrant(Document):
	"""Platform staff access to one tenant's ERP: asked with a reason and a scope, approved by the organisation's owner
	or admin, and ended automatically. Without one, platform staff have no login on the tenant."""

	def before_insert(self):
		self.requested_by = frappe.session.user
		self.status = "Requested"
		for f in ("decided_by", "valid_from", "valid_until", "tenant_user"):
			self.set(f, None)

	def validate(self):
		keep(self, DECIDED)
		problems = grant_findings(self.reason, self.hours, self.scope)
		if problems:
			frappe.throw("<br>".join(_(p) for p in problems))
		if frappe.db.get_value("Tenant", self.tenant, "status") not in ("Active", "Suspended"):
			frappe.throw(_("Access is asked only for a running tenant"))
		self.organization = frappe.db.get_value("Tenant", self.tenant, "organization")
		if self.is_new() and frappe.db.exists("Tenant Access Grant", {"tenant": self.tenant, "requested_by":
				frappe.session.user, "status": ["in", ["Requested", "Approved"]]}):
			frappe.throw(_("You already have an open request or access for this tenant"))

	def after_insert(self):
		from stemic_cloud.admin import tell_approvers
		from stemic_cloud.audit import log

		tell_approvers(self.organization, self)
		log("Access requested", organization=self.organization, tenant=self.tenant,
			reference=("Tenant Access Grant", self.name), details={"scope": self.scope, "hours": self.hours,
			"reason": self.reason})

	def on_trash(self):
		if self.status != "Requested":
			frappe.throw(_("A decided access request is kept"))

# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from stemic_cloud.guards import keep


class CloudOrganization(Document):
	"""An insurance company registered on the platform: its details, the terms it accepted, its subscription and
	tenant. Platform staff see this record, never the tenant's insurance data."""

	def validate(self):
		keep(self, ("preferred_subdomain", "owner_user", "terms_version", "terms_accepted_on", "terms_ip"))

	def on_trash(self):
		frappe.throw(_("An organisation is closed, never deleted"))

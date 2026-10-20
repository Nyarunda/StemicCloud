# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from stemic_cloud.guards import keep


class Tenant(Document):
	"""One customer ERP environment: a Frappe site with ERPNext and the insurance app at {subdomain}.{root domain}."""

	def validate(self):
		keep(self, ("site_name", "subdomain", "organization", "deployment_group", "status", "url", "admin_email",
			"read_only", "last_job", "health", "app_version"))

	def on_trash(self):
		frappe.throw(_("A tenant is archived, never deleted here (its site and backups are handled on the server)"))

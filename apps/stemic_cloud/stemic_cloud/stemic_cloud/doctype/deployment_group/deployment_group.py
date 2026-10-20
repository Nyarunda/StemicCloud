# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.model.document import Document


class DeploymentGroup(Document):
	"""Where tenants are created: a bench on a server, the apps installed on each new site, and how commands reach it.
	Phase 1 runs the bench on the platform's own server."""

	def validate(self):
		apps = [a.strip() for a in (self.apps or "").splitlines() if a.strip()]
		if not apps or apps[0] != "erpnext":
			frappe.throw(_("ERPNext is installed first"))
		bad = [a for a in apps if not a.replace("_", "").isalnum()]
		if bad:
			frappe.throw(_("Not an app name: {0}").format(", ".join(bad)))
		self.apps = "\n".join(apps)
		if self.runner == "Local Bench":
			if not self.bench_path or not os.path.isabs(self.bench_path):
				frappe.throw(_("Give the bench folder as a full path"))
			if not self.get_password("db_root_password", raise_exception=False):
				frappe.throw(_("Give the MariaDB root password"))
		if self.is_default:
			frappe.db.set_value("Deployment Group", {"name": ["!=", self.name], "is_default": 1}, "is_default", 0)

	def on_trash(self):
		if frappe.db.exists("Tenant", {"deployment_group": self.name}):
			frappe.throw(_("Tenants live on this group"))

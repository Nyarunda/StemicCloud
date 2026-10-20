# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

from frappe.model.document import Document


class TenantProvisioningJob(Document):
	"""The background job that creates a tenant, step by step; a failed job is retried from the failed step."""

	pass

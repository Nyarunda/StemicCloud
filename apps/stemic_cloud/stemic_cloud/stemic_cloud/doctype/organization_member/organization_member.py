# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

from frappe.model.document import Document


class OrganizationMember(Document):
	"""A person's role in an organisation on the portal (Owner, Admin, Billing Admin, Member). It gives no access to the tenant's ERP: the ERP's own users and roles do."""

	pass

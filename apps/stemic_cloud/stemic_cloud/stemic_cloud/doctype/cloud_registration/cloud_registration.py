# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

from frappe.model.document import Document


class CloudRegistration(Document):
	"""A registration waiting for its email to be verified (the link carries a token stored here hashed)."""

	pass

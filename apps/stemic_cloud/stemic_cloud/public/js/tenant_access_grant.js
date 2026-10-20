// The organisation approves on its portal (Security); staff can end their own access early.
frappe.ui.form.on("Tenant Access Grant", {
	refresh(frm) {
		if (frm.doc.status === "Requested") frm.set_intro(__("Waiting for the organisation's owner or admin to decide on the portal."));
		if (frm.doc.status === "Approved") {
			frm.set_intro(__("Log in to the tenant as {0} until {1}.", [frm.doc.tenant_user, frappe.datetime.str_to_user(frm.doc.valid_until)]), "green");
			if (frm.doc.requested_by === frappe.session.user || frappe.user.has_role("Platform Super Admin")) {
				frm.add_custom_button(__("End Access Now"), () => frappe.call({ method: "stemic_cloud.admin.end_my_access",
					args: { grant: frm.doc.name }, callback: () => frm.reload_doc() }));
			}
		}
	},
});

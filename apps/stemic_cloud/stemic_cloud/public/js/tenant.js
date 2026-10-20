// Platform staff reach a tenant's ERP only through an access request the organisation approves.
frappe.ui.form.on("Tenant", {
	refresh(frm) {
		if (frm.doc.url) frm.add_web_link(frm.doc.url, __("Open the site's address"));
		if (["Active", "Suspended"].includes(frm.doc.status) && frappe.user.has_role(["Platform Support", "Platform Super Admin"])) {
			frm.add_custom_button(__("Request Access"), () => {
				frappe.prompt([
					{ fieldname: "reason", fieldtype: "Small Text", label: __("Why (ticket or problem)"), reqd: 1 },
					{ fieldname: "scope", fieldtype: "Select", label: __("Scope"), options: "Read Only\nSupport (Read and Write)", default: "Read Only", reqd: 1 },
					{ fieldname: "hours", fieldtype: "Int", label: __("For (Hours)"), default: 4, reqd: 1 },
				], (v) => frappe.call({ method: "stemic_cloud.admin.request_access", args: { tenant: frm.doc.name, ...v },
					callback: (r) => frappe.set_route("Form", "Tenant Access Grant", r.message) }),
				__("Ask the organisation for access"), __("Ask"));
			});
		}
	},
});

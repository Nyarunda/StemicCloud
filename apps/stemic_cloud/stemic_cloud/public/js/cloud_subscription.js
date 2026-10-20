// Suspension is a person's decision after the grace period; the ERP becomes read-only, never unreadable.
frappe.ui.form.on("Cloud Subscription", {
	refresh(frm) {
		if (!["Past Due", "Grace"].includes(frm.doc.status)) return;
		if (!frappe.user.has_role(["Platform Finance", "Platform Super Admin", "System Manager"])) return;
		frm.add_custom_button(__("Suspend"), () => {
			frappe.prompt({ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1,
				description: __("The ERP becomes read-only until the invoice is paid; the customer is told by email.") },
				(v) => frappe.call({ method: "stemic_cloud.subscriptions.suspend", args: { subscription: frm.doc.name, reason: v.reason },
					freeze: true, callback: () => frm.reload_doc() }), __("Suspend the subscription"), __("Suspend"));
		});
	},
});

// Platform Finance records a payment (with its reference) or voids an unpaid invoice (with a reason).
frappe.ui.form.on("Subscription Invoice", {
	refresh(frm) {
		if (frm.doc.status !== "Issued" || !frappe.user.has_role(["Platform Finance", "Platform Super Admin", "System Manager"])) return;
		frm.add_custom_button(__("Mark Paid"), () => {
			frappe.prompt([
				{ fieldname: "reference", fieldtype: "Data", label: __("Payment Reference"), reqd: 1 },
				{ fieldname: "paid_on", fieldtype: "Date", label: __("Paid On"), default: frappe.datetime.get_today(), reqd: 1 },
			], (v) => frappe.call({ method: "stemic_cloud.subscriptions.mark_paid", args: { invoice: frm.doc.name, ...v },
				callback: () => frm.reload_doc() }), __("Record the payment"), __("Mark Paid"));
		}).addClass("btn-primary");
		frm.add_custom_button(__("Void"), () => {
			frappe.prompt({ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
				(v) => frappe.call({ method: "stemic_cloud.subscriptions.void_invoice", args: { invoice: frm.doc.name, reason: v.reason },
					callback: () => frm.reload_doc() }), __("Void the invoice"), __("Void"));
		});
	},
});

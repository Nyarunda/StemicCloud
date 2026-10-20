// A failed job is retried from the step that failed.
frappe.ui.form.on("Tenant Provisioning Job", {
	refresh(frm) {
		if (frm.doc.status === "Failed" && frappe.user.has_role(["Platform Support", "Platform Super Admin", "System Manager"])) {
			frm.add_custom_button(__("Retry From the Failed Step"), () =>
				frappe.call({ method: "stemic_cloud.provisioning.retry", args: { job: frm.doc.name },
					callback: () => { frappe.show_alert(__("Queued")); frm.reload_doc(); } })).addClass("btn-primary");
		}
		if (["Queued", "Running"].includes(frm.doc.status)) setTimeout(() => frm.reload_doc(), 10000);
	},
});

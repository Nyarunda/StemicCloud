"""Writes every Stemic Cloud doctype's JSON from the specification below (run it after changing a doctype; CI fails
when the written files are not committed). A controller stub is written only where none exists.

    python3 -I apps/stemic_cloud/tools/build_doctypes.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "stemic_cloud")
ROOT = os.path.join(APP, "stemic_cloud", "doctype")
MODULE = "Stemic Cloud"
STAMP = "2026-10-20 12:00:00.000000"

SA, SUP, FIN = "Platform Super Admin", "Platform Support", "Platform Finance"
FULL = {"read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "print": 1, "email": 1, "share": 1}
READ = {"read": 1, "report": 1, "print": 1}


def perms(*rows, submittable=False):
	"""System Manager and the Platform Super Admin may do everything; the other rows as given."""
	full = dict(FULL, **({"submit": 1, "cancel": 1, "amend": 1} if submittable else {}))
	return [{"role": "System Manager", **full}, {"role": SA, **full}, *rows]


# ---- field helpers


def f(fieldname, fieldtype, label=None, **kw):
	d = {"fieldname": fieldname, "fieldtype": fieldtype}
	if label:
		d["label"] = label
	d.update(kw)
	return d


def data(n, l, **k):
	return f(n, "Data", l, **k)


def link(n, l, opt, **k):
	return f(n, "Link", l, options=opt, **k)


def sel(n, l, opts, **k):
	return f(n, "Select", l, options="\n".join(opts), **k)


def cur(n, l, **k):
	return f(n, "Currency", l, options=k.pop("options", "currency"), precision="2", **k)


def num(n, l, **k):
	return f(n, "Int", l, **k)


def date(n, l, **k):
	return f(n, "Date", l, **k)


def dtm(n, l, **k):
	return f(n, "Datetime", l, **k)


def chk(n, l, **k):
	return f(n, "Check", l, **k)


def text(n, l, **k):
	return f(n, "Small Text", l, **k)


def table(n, l, opt, **k):
	return f(n, "Table", l, options=opt, **k)


def sec(n, l=None, **k):
	return f(n, "Section Break", l, **k)


def col(n):
	return f(n, "Column Break")


def ro(field):
	field["read_only"] = 1
	return field


def series(prefix):
	return f("naming_series", "Select", "Series", options=prefix, default=prefix, reqd=1)


def amended(dt):
	return ro(link("amended_from", "Amended From", dt, no_copy=1, print_hide=1))


ORG_TYPES = ["Insurance Broker", "Insurance Agency", "Insurer / Underwriter", "Managing General Agent",
	"Insurance Service Provider"]
SUB_STATUS = ["Trial", "Active", "Past Due", "Grace", "Suspended", "Cancelled"]
TENANT_STATUS = ["Reserved", "Provisioning", "Active", "Failed", "Suspended", "Archived"]

DT = []


def doctype(name, fields, **kw):
	DT.append({"name": name, "fields": fields, **kw})


doctype("Cloud Settings", issingle=True, doc="How the platform provisions tenants and bills them.", fields=[
	sec("platform_section", "Platform"),
	data("root_domain", "Root Domain", default="stemicinsurance.com", reqd=1,
		description="Tenants are {subdomain}.{root domain}; the portal is app.{root domain}."),
	data("portal_url", "Portal Address", default="https://app.stemicinsurance.com"),
	data("support_email", "Support Email", options="Email"),
	col("platform_col"),
	data("terms_version", "Terms Version", default="2026-10", reqd=1,
		description="The version a new organisation accepts; recorded on the organisation."),
	data("terms_url", "Terms Address"),
	sec("billing_section", "Subscriptions"),
	num("trial_days", "Trial (Days)", default="14"),
	num("grace_days", "Grace After an Unpaid Invoice (Days)", default="14",
		description="Reminders during the grace period; after it a Platform Finance user may suspend (the ERP stays "
			"readable)."),
	col("billing_col"),
	num("invoice_due_days", "Invoices Due After (Days)", default="7"),
	num("verification_hours", "Email Verification Valid For (Hours)", default="48"),
	num("invitation_days", "Invitations Valid For (Days)", default="7"),
	sec("security_section", "Security"),
	chk("watch_logins", "Alert on Unusual Logins", default="1"),
	link("security_alert_user", "Send Alerts To", "User"),
])

doctype("Plan Feature", istable=True, fields=[
	data("feature", "Feature", reqd=1, in_list_view=1), data("value", "Included", in_list_view=1,
		description="Yes, No, Basic, Advanced, a number...")])

doctype("Subscription Plan", autoname="field:plan_code", title="plan_name", search="plan_name",
	doc="A plan customers subscribe to: price per month or year, user limit and the features shown on the plans page.",
	perms=perms({"role": FIN, **FULL}, {"role": SUP, **READ}), fields=[
		data("plan_code", "Code", reqd=1, unique=1, in_list_view=1),
		data("plan_name", "Plan", reqd=1, in_list_view=1),
		chk("enabled", "Offered", default="1", in_list_view=1),
		chk("is_public", "On the Plans Page", default="1"),
		num("sort_order", "Order"),
		col("plan_col"),
		link("currency", "Currency", "Currency", reqd=1, default="USD"),
		cur("monthly_price", "Monthly Price", in_list_view=1),
		cur("annual_price", "Annual Price", description="Blank: twelve months."),
		num("max_users", "ERP Users", description="Blank: by contract."),
		num("trial_days", "Trial (Days)", description="Blank: Cloud Settings."),
		chk("contact_sales", "Contact Sales (No Self-Service)"),
		sec("features_section", "Features"),
		table("features", "Features", "Plan Feature"),
		text("description", "Description"),
	])

doctype("Cloud Onboarding Step", istable=True, fields=[
	ro(data("code", "Code", in_list_view=1)), ro(data("title", "Step", in_list_view=1)),
	ro(chk("done", "Done", in_list_view=1)), ro(link("done_by", "By", "User")), ro(dtm("done_on", "On"))])

doctype("Cloud Organization", autoname="naming_series:", title="org_name", search="org_name,business_email,status",
	doc="An insurance company registered on the platform: its details, the terms it accepted, its subscription and "
		"tenant. Platform staff see this record, never the tenant's insurance data.",
	perms=perms({"role": SUP, **READ, "write": 1}, {"role": FIN, **READ}), fields=[
		series("ORG-.#####"),
		data("org_name", "Company Name", reqd=1, in_list_view=1),
		sel("org_type", "Organization Type", ORG_TYPES, reqd=1, in_standard_filter=1),
		data("registration_number", "Registration Number"),
		link("country", "Country", "Country", default="Kenya"),
		link("currency", "Currency", "Currency", default="KES"),
		data("time_zone", "Time Zone", default="Africa/Nairobi"),
		col("org_col"),
		data("business_email", "Business Email", options="Email", reqd=1),
		data("phone", "Phone", options="Phone"),
		data("preferred_subdomain", "Subdomain", reqd=1),
		ro(sel("status", "Status", ["Active", "Suspended", "Closed"], default="Active", in_list_view=1,
			in_standard_filter=1)),
		ro(link("owner_user", "Owner", "User")),
		sec("terms_section", "Terms"),
		ro(data("terms_version", "Terms Accepted")), ro(dtm("terms_accepted_on", "Accepted On")),
		ro(data("terms_ip", "From Address")),
		sec("onboarding_section", "Onboarding"),
		ro(f("onboarding_progress", "Percent", "Progress")),
		ro(table("onboarding", "Steps", "Cloud Onboarding Step")),
	])

doctype("Cloud Registration", autoname="hash", title="org_name", in_create=True,
	doc="A registration waiting for its email to be verified (the link carries a token stored here hashed).",
	perms=perms({"role": SUP, **READ}), fields=[
		ro(data("email", "Email", options="Email", in_list_view=1)), ro(data("full_name", "Name")),
		ro(data("org_name", "Company", in_list_view=1)), ro(sel("org_type", "Type", ORG_TYPES)),
		ro(data("registration_number", "Registration Number")), ro(link("country", "Country", "Country")),
		ro(link("currency", "Currency", "Currency")), ro(data("time_zone", "Time Zone")),
		ro(data("phone", "Phone")), ro(data("subdomain", "Subdomain")), ro(link("plan", "Plan", "Subscription Plan")),
		ro(sel("billing_cycle", "Billing", ["Monthly", "Annual"])),
		ro(data("terms_version", "Terms")), ro(data("ip_address", "From Address")),
		ro(data("token_hash", "Token", hidden=1)), ro(dtm("expires_on", "Expires")),
		ro(sel("status", "Status", ["Pending", "Verified", "Expired"], default="Pending", in_list_view=1)),
		ro(link("organization", "Organization", "Cloud Organization")),
	])

doctype("Organization Member", autoname="hash", title="user", search="organization,user,role",
	doc="A person's role in an organisation on the portal (Owner, Admin, Billing Admin, Member). It gives no access to "
		"the tenant's ERP: the ERP's own users and roles do.",
	perms=perms({"role": SUP, **READ}), fields=[
		link("organization", "Organization", "Cloud Organization", reqd=1, in_list_view=1, in_standard_filter=1),
		link("user", "User", "User", reqd=1, in_list_view=1),
		sel("role", "Role", ["Owner", "Admin", "Billing Admin", "Member"], reqd=1, in_list_view=1),
		sel("status", "Status", ["Active", "Removed"], default="Active", in_list_view=1, in_standard_filter=1),
		ro(link("added_by", "Added By", "User")), ro(dtm("joined_on", "Joined")),
	])

doctype("Organization Invitation", autoname="hash", title="email", in_create=True,
	doc="An invitation to join an organisation on the portal, by email, with a role; the link's token is stored hashed.",
	perms=perms({"role": SUP, **READ}), fields=[
		ro(link("organization", "Organization", "Cloud Organization", in_list_view=1, in_standard_filter=1)),
		ro(data("email", "Email", options="Email", in_list_view=1)),
		ro(sel("role", "Role", ["Owner", "Admin", "Billing Admin", "Member"], in_list_view=1)),
		ro(sel("status", "Status", ["Pending", "Accepted", "Revoked", "Expired"], default="Pending", in_list_view=1)),
		ro(link("invited_by", "Invited By", "User")), ro(dtm("expires_on", "Expires")),
		ro(data("token_hash", "Token", hidden=1)), ro(link("accepted_by", "Accepted By", "User")),
	])

doctype("Cloud Subscription", autoname="naming_series:", title="organization", search="organization,plan,status",
	doc="An organisation's plan, cycle and standing. A missed payment moves it to Past Due and Grace with reminders; "
		"suspension is done by a Platform Finance user after the grace period, never by the machine alone.",
	perms=perms({"role": FIN, **FULL}, {"role": SUP, **READ}), fields=[
		series("SUB-.#####"),
		link("organization", "Organization", "Cloud Organization", reqd=1, in_list_view=1, in_standard_filter=1),
		link("plan", "Plan", "Subscription Plan", reqd=1, in_list_view=1, in_standard_filter=1),
		sel("billing_cycle", "Billing", ["Monthly", "Annual"], default="Monthly", reqd=1),
		ro(sel("status", "Status", SUB_STATUS, default="Trial", in_list_view=1, in_standard_filter=1)),
		col("sub_col"),
		date("start_date", "Started", reqd=1, default="Today"),
		date("trial_ends_on", "Trial Ends"),
		ro(date("current_period_start", "Period From")), ro(date("current_period_end", "Period To")),
		ro(link("currency", "Currency", "Currency")),
		sec("usage_section", "Usage"),
		ro(num("active_users", "Active ERP Users")), ro(dtm("usage_checked_on", "Counted On")),
		col("usage_col"),
		ro(text("seat_warning", "Over the Plan")),
		sec("end_section", "Ending", collapsible=1),
		ro(date("cancelled_on", "Cancelled On")), ro(text("cancel_reason", "Why")),
		ro(link("suspended_by", "Suspended By", "User")), ro(dtm("suspended_on", "Suspended On")),
	])

doctype("Subscription Invoice", autoname="naming_series:", title="organization", search="organization,status",
	doc="One period of a subscription billed. Marked paid with the payment reference by Platform Finance (payment "
		"collection by M-Pesa and card comes in phase 2).",
	perms=perms({"role": FIN, **FULL}, {"role": SUP, **READ}), fields=[
		series("SINV-.#####"),
		link("subscription", "Subscription", "Cloud Subscription", reqd=1),
		ro(link("organization", "Organization", "Cloud Organization", fetch_from="subscription.organization",
			in_list_view=1, in_standard_filter=1)),
		ro(link("plan", "Plan", "Subscription Plan")),
		date("period_start", "Period From", reqd=1), date("period_end", "Period To", reqd=1),
		col("inv_col"),
		ro(link("currency", "Currency", "Currency")),
		cur("amount", "Amount", reqd=1, in_list_view=1),
		date("due_date", "Due", reqd=1, in_list_view=1),
		ro(sel("status", "Status", ["Issued", "Paid", "Void"], default="Issued", in_list_view=1, in_standard_filter=1)),
		sec("payment_section", "Payment"),
		ro(date("paid_on", "Paid On")), ro(data("payment_reference", "Reference")),
		ro(link("recorded_by", "Recorded By", "User")),
	])

doctype("Deployment Group", autoname="field:group_name", title="group_name",
	doc="Where tenants are created: a bench on a server, the apps installed on each new site, and how commands reach "
		"it. Phase 1 runs the bench on the platform's own server.",
	perms=perms({"role": SUP, **READ}), fields=[
		data("group_name", "Name", reqd=1, unique=1, in_list_view=1),
		chk("is_default", "Default for New Tenants", in_list_view=1),
		chk("enabled", "Takes New Tenants", default="1"),
		sel("runner", "Runs Commands", ["Local Bench", "Dry Run"], default="Dry Run", reqd=1,
			description="Dry Run records each command without running it (for testing the portal)."),
		data("bench_path", "Bench Folder", description="For example /home/frappe/frappe-bench."),
		col("dg_col"),
		text("apps", "Apps on Each Site", default="erpnext\ninsurance", reqd=1, description="One per line, in order."),
		f("db_root_password", "Password", "MariaDB Root Password"),
		data("health_base", "Health Check Through",
			description="Blank: https://{site}. On one server, for example http://127.0.0.1:8000 with the site as "
				"Host."),
		num("max_tenants", "At Most (Tenants)"),
		chk("setup_nginx", "Write nginx After Each Site", default="1"),
	])

doctype("Tenant", autoname="field:site_name", title="site_name", search="organization,status", in_create=True,
	doc="One customer ERP environment: a Frappe site with ERPNext and the insurance app at {subdomain}.{root domain}.",
	perms=perms({"role": SUP, **READ, "write": 1}, {"role": FIN, **READ}), fields=[
		ro(data("site_name", "Site", unique=1, in_list_view=1)),
		ro(data("subdomain", "Subdomain", unique=1)),
		ro(link("organization", "Organization", "Cloud Organization", in_list_view=1, in_standard_filter=1)),
		ro(link("deployment_group", "Deployment Group", "Deployment Group")),
		ro(sel("status", "Status", TENANT_STATUS, default="Reserved", in_list_view=1, in_standard_filter=1)),
		col("tenant_col"),
		ro(data("url", "Address")), ro(data("app_version", "Insurance App Version")),
		ro(data("admin_email", "Administrator")),
		sec("health_section", "Health"),
		ro(sel("health", "Health", ["Unknown", "Healthy", "Unreachable"], default="Unknown", in_list_view=1)),
		ro(dtm("last_health_check", "Checked")), ro(dtm("last_backup_on", "Last Backup")),
		col("health_col"),
		ro(link("last_job", "Last Provisioning Job", "Tenant Provisioning Job")),
		ro(chk("read_only", "Read Only (Suspended)")),
	])

doctype("Provisioning Step Log", istable=True, fields=[
	ro(data("code", "Code")), ro(data("title", "Step", in_list_view=1)),
	ro(sel("status", "Status", ["Pending", "Running", "Done", "Failed", "Skipped"], default="Pending", in_list_view=1)),
	ro(text("command", "Command")), ro(dtm("started_on", "Started")), ro(dtm("ended_on", "Ended")),
	ro(f("output", "Long Text", "Output", in_list_view=0))])

doctype("Tenant Provisioning Job", autoname="naming_series:", title="tenant", in_create=True,
	doc="The background job that creates a tenant, step by step; a failed job is retried from the failed step.",
	perms=perms({"role": SUP, **READ}), fields=[
		series("PROV-.#####"),
		ro(link("tenant", "Tenant", "Tenant", in_list_view=1, in_standard_filter=1)),
		ro(sel("status", "Status", ["Queued", "Running", "Succeeded", "Failed"], default="Queued", in_list_view=1,
			in_standard_filter=1)),
		ro(num("attempts", "Attempts")), ro(dtm("started_on", "Started")), ro(dtm("ended_on", "Ended")),
		ro(text("error", "Error")),
		sec("steps_section", "Steps"),
		ro(table("steps", "Steps", "Provisioning Step Log")),
	])

doctype("Tenant Access Grant", autoname="naming_series:", title="tenant",
	doc="Platform staff access to one tenant's ERP: asked with a reason and a scope, approved by the organisation's "
		"owner or admin, and ended automatically. Without one, platform staff have no login on the tenant.",
	perms=perms({"role": SUP, **READ, "write": 1, "create": 1}), fields=[
		series("ACC-.#####"),
		link("tenant", "Tenant", "Tenant", reqd=1, in_list_view=1, in_standard_filter=1),
		ro(link("organization", "Organization", "Cloud Organization", fetch_from="tenant.organization")),
		ro(link("requested_by", "Requested By", "User")),
		text("reason", "Reason", reqd=1),
		sel("scope", "Scope", ["Read Only", "Support (Read and Write)"], default="Read Only", reqd=1),
		num("hours", "For (Hours)", default="4", reqd=1),
		col("grant_col"),
		ro(sel("status", "Status", ["Requested", "Approved", "Rejected", "Expired", "Revoked"], default="Requested",
			in_list_view=1, in_standard_filter=1)),
		ro(link("decided_by", "Decided By", "User")), ro(dtm("valid_from", "From")), ro(dtm("valid_until", "Until")),
		ro(data("tenant_user", "Login on the Tenant")),
	])

doctype("Cloud Audit Log", autoname="hash", title="action", in_create=True,
	doc="What was done on the platform, by whom, from where: append-only.",
	perms=[{"role": "System Manager", **READ}, {"role": SA, **READ}, {"role": SUP, **READ}, {"role": FIN, **READ}],
	fields=[
		ro(dtm("at", "At", in_list_view=1)), ro(link("actor", "By", "User", in_list_view=1, in_standard_filter=1)),
		ro(data("action", "Action", in_list_view=1, in_standard_filter=1)),
		ro(link("organization", "Organization", "Cloud Organization", in_standard_filter=1)),
		ro(link("tenant", "Tenant", "Tenant")),
		ro(link("reference_doctype", "Document Type", "DocType")),
		ro(f("reference_name", "Dynamic Link", "Document", options="reference_doctype")),
		ro(data("ip_address", "From Address")), ro(text("details", "Details")),
	])


# ---- building


def build(spec):
	meta = {"actions": [], "creation": STAMP, "doctype": "DocType", "engine": "InnoDB",
		"field_order": [x["fieldname"] for x in spec["fields"]], "fields": spec["fields"], "links": [],
		"modified": STAMP, "modified_by": "Administrator", "module": MODULE, "name": spec["name"],
		"owner": "Administrator", "sort_field": "creation", "sort_order": "DESC", "states": [],
		"permissions": [] if spec.get("istable") else spec.get("perms", perms())}
	for key, out in (("autoname", "autoname"), ("title", "title_field"), ("search", "search_fields")):
		if spec.get(key):
			meta[out] = spec[key]
	auto = spec.get("autoname", "")
	meta.update({"naming_rule": "By fieldname"} if auto.startswith("field:") else {"naming_rule":
		'By "Naming Series" field'} if auto.startswith("naming_series") else {"naming_rule": "Random"} if auto == "hash"
		else {})
	if spec.get("title"):
		meta["show_title_field_in_link"] = 1
	if spec.get("istable"):
		meta.update({"istable": 1, "editable_grid": 1})
	else:
		meta["track_changes"] = 1
	if spec.get("issingle"):
		meta["issingle"] = 1
		meta["permissions"] = [{"role": r, "read": 1, "write": 1, "create": 1} for r in ("System Manager", SA)]
	if spec.get("in_create"):
		meta["in_create"] = 1
	if spec.get("doc"):
		meta["description"] = spec["doc"]
	return meta


def check(specs):
	names = {s["name"] for s in specs}
	errors = []
	for s in specs:
		seen = set()
		for fld in s["fields"]:
			if fld["fieldname"] in seen:
				errors.append(f"{s['name']}: field {fld['fieldname']} twice")
			seen.add(fld["fieldname"])
			if fld["fieldtype"] == "Table" and fld["options"] not in names:
				errors.append(f"{s['name']}: table {fld['options']} is not specified")
	return errors


def scrub(name):
	return name.lower().replace(" ", "_").replace("-", "_")


CONTROLLER = '''# Copyright (c) 2026, Nyarunda
# For license information, please see license.txt

from frappe.model.document import Document


class {cls}(Document):
	"""{doc}"""

	pass
'''


def main():
	errors = check(DT)
	if errors:
		print("\n".join(errors))
		sys.exit(1)
	for spec in DT:
		folder = os.path.join(ROOT, scrub(spec["name"]))
		os.makedirs(folder, exist_ok=True)
		init = os.path.join(folder, "__init__.py")
		if not os.path.exists(init):
			open(init, "w").close()
		with open(os.path.join(folder, scrub(spec["name"]) + ".json"), "w") as out:
			json.dump(build(spec), out, indent=1, sort_keys=True)
			out.write("\n")
		controller = os.path.join(folder, scrub(spec["name"]) + ".py")
		if not os.path.exists(controller):
			with open(controller, "w") as out:
				out.write(CONTROLLER.format(cls=spec["name"].replace(" ", ""), doc=spec.get("doc", spec["name"])))
	print(f"{len(DT)} doctypes")


if __name__ == "__main__":
	main()

"""Writes the platform administration's desk: the Stemic Cloud workspace with its number cards, the sidebar and the
dock. Run after changing it; CI fails when the written files are not committed.

    python3 -I apps/stemic_cloud/tools/build_navigation.py
"""

import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "stemic_cloud")
PKG = os.path.join(APP, "stemic_cloud")
APP_NAME, MODULE = "stemic_cloud", "Stemic Cloud"
STAMP = "2026-10-20 12:00:00.000000"


def base(doctype, name, module=None, **values):
	doc = {"creation": STAMP, "docstatus": 0, "doctype": doctype, "idx": 0, "modified": STAMP,
		"modified_by": "Administrator", "name": name, "owner": "Administrator", **values}
	if module:
		doc["module"] = module
	return doc


def write(path, doc):
	"""Keeps the file's `modified` while nothing else changes (migrate re-imports only a newer file)."""
	os.makedirs(os.path.dirname(path), exist_ok=True)
	previous = None
	if os.path.exists(path):
		with open(path) as fh:
			previous = json.load(fh)
	strip = lambda d: {k: v for k, v in d.items() if k != "modified"}  # noqa: E731
	if previous and strip(previous) == strip(json.loads(json.dumps(doc))):
		doc["modified"] = previous.get("modified", doc["modified"])
	elif previous:
		doc["modified"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.000000")
	with open(path, "w") as out:
		json.dump(doc, out, indent=1, sort_keys=True, ensure_ascii=False)
		out.write("\n")


def scrub(name):
	return name.lower().replace(" ", "_").replace("-", "_")


def place(kind, name):
	return os.path.join(PKG, kind, scrub(name), scrub(name) + ".json")


CARDS = [  # (label, doctype, filters, function, field, color) or (label, method) for a custom card
	("Organizations", "Cloud Organization", [["status", "=", "Active"]], "Count", None, "#2F80ED"),
	("Active Subscriptions", "Cloud Subscription", [["status", "=", "Active"]], "Count", None, "#27AE60"),
	("Trial Organizations", "Cloud Subscription", [["status", "=", "Trial"]], "Count", None, "#9B51E0"),
	("Past Due or Grace", "Cloud Subscription", [["status", "in", ["Past Due", "Grace"]]], "Count", None, "#F2994A"),
	("Suspended Subscriptions", "Cloud Subscription", [["status", "=", "Suspended"]], "Count", None, "#EB5757"),
	("Active Tenants", "Tenant", [["status", "=", "Active"]], "Count", None, "#27AE60"),
	("Tenants With Alerts", "Tenant", [["health", "=", "Unreachable"]], "Count", None, "#EB5757"),
	("Failed Provisioning", "Tenant Provisioning Job", [["status", "=", "Failed"]], "Count", None, "#EB5757"),
	("Outstanding Invoices", "Subscription Invoice", [["status", "=", "Issued"]], "Sum", "amount", "#F2994A"),
	("Monthly Recurring Revenue", "stemic_cloud.admin.mrr_card"),
]

LINKS = [  # (section, [(label, doctype, filters)])
	("Customers", [("Organizations", "Cloud Organization", None), ("Members", "Organization Member", None),
		("Invitations", "Organization Invitation", None), ("Registrations", "Cloud Registration", None)]),
	("Tenants", [("Tenants", "Tenant", None), ("Provisioning Jobs", "Tenant Provisioning Job", None),
		("Failed Jobs", "Tenant Provisioning Job", [["status", "=", "Failed"]]),
		("Deployment Groups", "Deployment Group", None), ("Access Grants", "Tenant Access Grant", None)]),
	("Billing", [("Subscriptions", "Cloud Subscription", None), ("Invoices", "Subscription Invoice", None),
		("Unpaid Invoices", "Subscription Invoice", [["status", "=", "Issued"]]), ("Plans", "Subscription Plan", None)]),
	("Platform", [("Audit Log", "Cloud Audit Log", None), ("Settings", "Cloud Settings", None),
		("Users", "User", None), ("Activity Log", "Activity Log", None)]),
]
ICONS = {"Customers": "building-2", "Tenants": "server", "Billing": "receipt", "Platform": "settings"}


def number_card(card):
	if len(card) == 2:
		label, method = card
		return base("Number Card", label, MODULE, type="Custom", method=method, label=label, is_public=1,
			is_standard=1, color="#2F80ED", filters_json="[]", dynamic_filters_json="[]", show_percentage_stats=0,
			stats_time_interval="Monthly", function="Count", document_type="", aggregate_function_based_on="")
	label, doctype, flt, function, field, color = card
	return base("Number Card", label, MODULE, type="Document Type", document_type=doctype, function=function,
		aggregate_function_based_on=field or "", filters_json=json.dumps([[doctype, *f] for f in flt]),
		dynamic_filters_json="[]", is_public=1, is_standard=1, label=label, color=color, show_percentage_stats=1,
		stats_time_interval="Monthly")


def workspace():
	content = [{"id": "head", "type": "header", "data": {"text": '<span class="h4"><b>Stemic Cloud</b></span>',
		"col": 12}}, {"id": "note", "type": "paragraph", "data": {"text": "Organisations, subscriptions, tenants and "
		"their provisioning. Platform staff see these records, never a tenant's insurance data.", "col": 12}}]
	content += [{"id": f"nc{i}", "type": "number_card", "data": {"number_card_name": c[0], "col": 3}}
		for i, c in enumerate(CARDS)]
	links = []
	for i, (section, items) in enumerate(LINKS):
		plain = [x for x in items if not x[2]]
		links.append({"hidden": 0, "is_query_report": 0, "label": section, "link_count": len(plain),
			"link_type": "DocType", "onboard": 0, "type": "Card Break"})
		links += [{"hidden": 0, "is_query_report": 0, "label": label, "link_count": 0, "link_to": dt,
			"link_type": "DocType", "onboard": 0, "type": "Link"} for label, dt, _f in plain]
		content.append({"id": f"cd{i}", "type": "card", "data": {"card_name": section, "col": 3}})
	shortcuts = [{"color": "Grey", "doc_view": "List", "label": label, "link_to": dt, "type": "DocType"}
		for label, dt in (("Organizations", "Cloud Organization"), ("Tenants", "Tenant"),
			("Unpaid Invoices", "Subscription Invoice"), ("Audit Log", "Cloud Audit Log"))]
	return base("Workspace", MODULE, MODULE, app=APP_NAME, charts=[], content=json.dumps(content), custom_blocks=[],
		for_user="", hide_custom=0, icon="cloud", is_hidden=0, label=MODULE, links=links, number_cards=[{
		"label": c[0], "number_card_name": c[0]} for c in CARDS], parent_page="", public=1, quick_lists=[],
		restrict_to_domain="", roles=[{"role": r} for r in ("Platform Super Admin", "Platform Support",
			"Platform Finance", "System Manager")], sequence_id=1.0, shortcuts=shortcuts, standard=1, title=MODULE,
		type="Workspace")


def item(label, link_type=None, link_to=None, icon=None, type="Link", child=0, indent=0, collapsible=0,
		filters=None):
	row = {"added": 0, "child": child, "collapsible": collapsible, "hidden": 0, "icon": icon or "", "indent": indent,
		"is_default_module": 0, "keep_closed": 0, "label": label, "open_in_new_tab": 0, "show_arrow": 0, "type": type}
	if link_type:
		row.update({"link_type": link_type, "link_to": link_to})
	if filters:
		row["filters"] = json.dumps([[link_to, *f] for f in filters])
	return row


def sidebar():
	items = [item("Home", "Workspace", MODULE, "house")]
	for section, links in LINKS:
		items.append(item(section, icon=ICONS[section], type="Section Break", indent=1, collapsible=1))
		items += [item(label, "DocType", dt, child=1, filters=f) for label, dt, f in links]
	return base("Sidebar", MODULE, MODULE, app=APP_NAME, header_icon="cloud", items=items, standard=1, title=MODULE)


def dock():
	return base("Dock", APP_NAME, app=APP_NAME, items=[{"added": 0, "hidden": 0, "icon": "cloud", "link_to": MODULE,
		"link_type": "Sidebar", "title": MODULE}], standard=1, user="")


def main():
	write(place("workspace", MODULE), workspace())
	write(place("sidebar", MODULE), sidebar())
	write(os.path.join(APP, "dock", APP_NAME, APP_NAME + ".json"), dock())
	for c in CARDS:
		write(place("number_card", c[0]), number_card(c))
	print(f"workspace, sidebar, dock, {len(CARDS)} number cards")


if __name__ == "__main__":
	main()

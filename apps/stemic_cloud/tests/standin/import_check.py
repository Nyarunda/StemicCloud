"""Imports every module of the app against a stand-in for Frappe, so a typo or a missing name is caught without a
site. Run: python3 -I apps/stemic_cloud/tests/standin/import_check.py"""

import importlib
import os
import pkgutil
import sys
from unittest import mock

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, APP)


class Base:
	def __init__(self, *a, **kw):
		self.__dict__.update(kw)


frappe = mock.MagicMock(name="frappe")
frappe.whitelist = lambda *a, **k: (lambda f: f)
for name in ("frappe", "frappe.model", "frappe.model.document", "frappe.utils", "frappe.utils.password",
		"frappe.custom", "frappe.custom.doctype", "frappe.custom.doctype.custom_field",
		"frappe.custom.doctype.custom_field.custom_field", "frappe.rate_limiter", "frappe.sessions",
		"frappe.desk", "frappe.desk.form", "frappe.desk.form.assign_to"):
	sys.modules[name] = frappe if name == "frappe" else mock.MagicMock(name=name)
sys.modules["frappe.model.document"].Document = Base

import stemic_cloud  # noqa: E402

failed = []
for info in pkgutil.walk_packages(stemic_cloud.__path__, "stemic_cloud."):
	try:
		importlib.import_module(info.name)
	except Exception as e:  # noqa: BLE001
		failed.append(f"{info.name}: {type(e).__name__}: {e}")
print("Import failures:", "none" if not failed else "\n" + "\n".join(failed))
sys.exit(1 if failed else 0)

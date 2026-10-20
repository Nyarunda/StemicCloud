"""Runs bench commands for a deployment group: as a list of arguments (never through a shell), in the bench folder,
with a time limit, secrets given separately and hidden in what is logged. "Dry Run" records the command and succeeds,
for testing the portal without a bench."""

import json
import os
import subprocess
import urllib.request

import frappe
from frappe import _

from stemic_cloud.rules.provisioning_rules import filled, shown

TIMEOUT = 1800  # seconds: a new site with ERPNext takes several minutes


class RunError(Exception):
	pass


def group_secrets(group) -> dict:
	return {"db_root_password": group.get_password("db_root_password", raise_exception=False) or ""}


def run(group, argv: list[str], secrets: dict | None = None, timeout: int = TIMEOUT) -> str:
	"""`bench <argv>` in the group's bench folder; returns its output, raises RunError with the output on failure."""
	command = "bench " + " ".join(shown(argv))
	if group.runner == "Dry Run":
		return f"(dry run) {command}"
	if group.runner != "Local Bench":
		raise RunError(_("Unknown runner {0}").format(group.runner))
	path = group.bench_path or ""
	if not os.path.isdir(os.path.join(path, "sites")):
		raise RunError(_("{0} is not a bench folder").format(path))
	try:
		done = subprocess.run(["bench", *filled(argv, {**group_secrets(group), **(secrets or {})})], cwd=path,
			capture_output=True, text=True, timeout=timeout, env={**os.environ, "CI": "1"})
	except subprocess.TimeoutExpired as e:
		raise RunError(_("{0} took longer than {1} seconds").format(command, timeout)) from e
	except KeyError as e:
		raise RunError(str(e)) from e
	output = _hide((done.stdout or "") + (done.stderr or ""), {**group_secrets(group), **(secrets or {})})
	if done.returncode != 0:
		raise RunError(f"{command}\n{output[-4000:]}")
	return output[-8000:]


def _hide(text: str, secrets: dict) -> str:
	for value in secrets.values():
		if value:
			text = text.replace(value, "***")
	return text


def check_health(group, site: str) -> tuple[bool, str]:
	"""GET /api/method/ping on the site (directly, or through the group's address with the site as Host)."""
	if group.runner == "Dry Run":
		return True, "(dry run) ping"
	base = (group.health_base or f"https://{site}").rstrip("/")
	req = urllib.request.Request(base + "/api/method/ping", headers={"Host": site} if group.health_base else {})
	try:
		with urllib.request.urlopen(req, timeout=20) as r:
			body = json.loads(r.read().decode() or "{}")
			return body.get("message") == "pong", f"HTTP {r.status} {body}"
	except Exception as e:
		return False, str(e)


def result_of(output: str):
	"""The value a `bench execute` printed (its last line, as JSON when it is)."""
	lines = [x for x in (output or "").strip().splitlines() if x.strip()]
	if not lines:
		return None
	try:
		return json.loads(lines[-1])
	except ValueError:
		return lines[-1].strip().strip('"')


def group_for_new_tenant():
	name = frappe.db.get_value("Deployment Group", {"is_default": 1, "enabled": 1}, "name") or frappe.db.get_value(
		"Deployment Group", {"enabled": 1}, "name")
	if not name:
		frappe.throw(_("No deployment group takes new tenants"))
	group = frappe.get_doc("Deployment Group", name)
	if group.max_tenants and frappe.db.count("Tenant", {"deployment_group": name, "status": ["!=", "Archived"]}) >= \
			group.max_tenants:
		frappe.throw(_("Deployment group {0} is full").format(name))
	return group

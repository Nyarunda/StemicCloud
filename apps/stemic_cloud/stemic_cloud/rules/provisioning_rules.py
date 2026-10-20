"""The steps that turn a subscription into a running ERP site, as data: each step is a command (an argument list, never
a shell string) or an HTTP check, so the plan can be tested, shown, logged with its secrets hidden, and resumed from
the step that failed.

A tenant is a Frappe site on the deployment group's bench, with ERPNext and the insurance app; the site's database
is made by `bench new-site`. Nothing here talks to a server."""

from dataclasses import dataclass, field

SECRET = "\x00secret:"  # marks an argument the runner fills from a secret and the log shows as ***

BUSINESS_TYPE = {"Insurance Broker": "Broker", "Insurance Agency": "Agency", "Insurer / Underwriter": "Insurer",
	"Managing General Agent": "Agency", "Insurance Service Provider": "Broker"}


APP_TITLE = {"erpnext": "ERPNext", "insurance": "the insurance app"}


@dataclass
class Step:
	code: str
	title: str
	kind: str  # "bench": run `bench` with argv in the bench folder; "http": GET url, expect 200; "record": no command
	argv: list[str] = field(default_factory=list)
	url: str = ""
	optional: bool = False  # a failure is logged and the plan goes on (nginx reload, a welcome email)


def secret(name: str) -> str:
	return SECRET + name


def plan(site: str, apps: list[str], admin_email: str, admin_first_name: str, business_type: str,
		host_url: str, health_url: str, reload_web: bool = True) -> list[Step]:
	"""The provisioning plan for one tenant site."""
	steps = [
		Step("reserve", "Reserve your address", "record"),
		Step("new_site", "Create the site and its database", "bench", ["new-site", site,
			"--db-root-password", secret("db_root_password"), "--admin-password", secret("admin_password"),
			]),
	]
	for app in apps:
		steps.append(Step(f"install_{app}", f"Install {APP_TITLE.get(app, app)}", "bench", ["--site", site, "install-app", app]))
	steps += [
		Step("migrate", "Bring the database up to date", "bench", ["--site", site, "migrate"]),
		Step("host_name", "Point the address at it", "bench", ["--site", site, "set-config", "host_name", host_url]),
		Step("business_type", "Set the insurance business type", "bench", ["--site", site, "execute",
			"frappe.client.set_value", "--kwargs",
			'{"doctype": "Insurance Settings", "name": "Insurance Settings", "fieldname": "business_type", "value": "'
			+ BUSINESS_TYPE.get(business_type, "Broker") + '"}']) if "insurance" in apps else None,
		Step("admin_user", "Create your administrator login", "bench", ["--site", site, "add-user",
			admin_email, "--first-name", admin_first_name or "Admin", "--user-type", "System User", "--add-role",
			"System Manager", *(["--add-role", "Insurance Administrator"] if "insurance" in apps else [])]),
		Step("scheduler", "Turn on reminders and daily jobs", "bench", ["--site", site, "enable-scheduler"]),
		Step("backup", "Take the first backup", "bench", ["--site", site, "backup"], optional=True),
		Step("web", "Put it on the web", "bench", ["setup", "nginx", "--yes"], optional=True)
		if reload_web else None,
		Step("health", "Check that it answers", "http", url=health_url),
		Step("invite", "Email you a link to set your password", "bench", ["--site", site, "execute",
			"frappe.core.doctype.user.user.reset_password", "--kwargs", '{"user": "' + admin_email + '"}'],
			optional=True),
		Step("activate", "Open it for use", "record"),
	]
	return [s for s in steps if s is not None]


def shown(argv: list[str]) -> list[str]:
	"""The command as the log may show it: secrets as ***."""
	return ["***" if a.startswith(SECRET) else a for a in argv]


def filled(argv: list[str], secrets: dict) -> list[str]:
	"""The command as it runs: each secret marker replaced by its value (a missing secret is an error)."""
	out = []
	for a in argv:
		if a.startswith(SECRET):
			name = a[len(SECRET):]
			if not secrets.get(name):
				raise KeyError(f"secret {name} is not set")
			out.append(secrets[name])
		else:
			out.append(a)
	return out


def resume_from(steps: list[Step], done: list[str]) -> list[Step]:
	"""The steps still to run after the ones that succeeded (a failed job is retried from where it stopped)."""
	finished = set(done)
	return [s for s in steps if s.code not in finished]


def email_safe(email: str) -> bool:
	"""An address fit to put in a command's JSON argument (no quotes, spaces or control characters)."""
	import re

	return bool(re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", email or ""))


# ---- commands on a running tenant


def suspend(site: str) -> list[list[str]]:
	"""Suspension keeps the ERP readable: maintenance mode with reads allowed."""
	return [["--site", site, "set-config", "allow_reads_during_maintenance", "1", "--parse"],
		["--site", site, "set-maintenance-mode", "on"]]


def resume(site: str) -> list[list[str]]:
	return [["--site", site, "set-maintenance-mode", "off"]]


def grant_user(site: str, email: str, first_name: str, roles: list[str]) -> list[str]:
	argv = ["--site", site, "add-user", email, "--first-name", first_name, "--user-type", "System User"]
	for r in roles:
		argv += ["--add-role", r]
	return argv


def revoke_user(site: str, email: str) -> list[str]:
	return ["--site", site, "disable-user", email]


def count_users(site: str) -> list[str]:
	return ["--site", site, "execute", "frappe.client.get_count", "--kwargs",
		'{"doctype": "User", "filters": {"enabled": 1, "user_type": "System User", "name": ["not in", '
		'["Administrator", "Guest"]]}}']


def app_version(site: str, app: str = "insurance") -> list[str]:
	return ["--site", site, "execute", "frappe.get_attr", "--args", f'["{app}.__version__"]']

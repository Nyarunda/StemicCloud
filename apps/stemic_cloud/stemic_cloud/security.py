"""Login monitoring for the portal and the platform desk: a login from a network the person never used, or outside
working hours, is written to the audit log and emailed to the person in Cloud Settings. Frappe does the rest: password
policy, lockout after failed attempts (System Settings), two-factor login, and the Activity Log."""

import frappe
from frappe.utils import add_months, now_datetime

from stemic_cloud.rules.login_rules import login_findings


def on_login(login_manager=None):
	try:
		s = frappe.get_cached_doc("Cloud Settings")
		user = frappe.session.user
		if not s.watch_logins or user in ("Administrator", "Guest"):
			return
		ip = getattr(frappe.local, "request_ip", None)
		known = frappe.get_all("Activity Log", filters={"user": user, "operation": "Login", "status": "Success",
			"creation": [">", add_months(now_datetime(), -6)]}, pluck="ip_address", limit=200)
		known = [k for k in known if k and k != ip] if known.count(ip) <= 1 else known
		reasons = login_findings(ip or "", known, now_datetime(), None)
		if reasons:
			from stemic_cloud.audit import log

			log("Unusual login", details={"user": user, "ip": ip, "why": reasons}, actor=user)
			if s.security_alert_user:
				email = frappe.db.get_value("User", s.security_alert_user, "email")
				if email:
					frappe.sendmail(recipients=[email], subject=f"Unusual login: {user}", message=", ".join(reasons))
	except Exception:
		frappe.log_error(title="Stemic Cloud: login check")

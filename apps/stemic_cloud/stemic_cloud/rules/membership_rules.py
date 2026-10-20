"""Organisation roles in the portal, kept apart from the ERP's own roles: billing, team and ERP environment rights.
Membership never grants anything inside a tenant's ERP; the tenant's own users and roles do."""

import datetime
import hashlib
import hmac

OWNER, ADMIN, BILLING, MEMBER = "Owner", "Admin", "Billing Admin", "Member"
ROLES = (OWNER, ADMIN, BILLING, MEMBER)

ALLOWED = {
	"view": ROLES,
	"view_billing": (OWNER, ADMIN, BILLING),
	"pay": (OWNER, BILLING),
	"change_plan": (OWNER,),
	"cancel": (OWNER,),
	"manage_team": (OWNER, ADMIN),
	"manage_erp": (OWNER, ADMIN),
	"request_export": (OWNER,),
	"approve_access": (OWNER, ADMIN),
	"onboarding": (OWNER, ADMIN),
}


def can(role: str | None, action: str) -> bool:
	return bool(role) and role in ALLOWED.get(action, ())


def role_change_findings(actor_role: str, target_role: str, new_role: str | None, owners: int) -> list[str]:
	"""Changing or removing (new_role None) a member: admins manage members and admins, only an owner manages
	owners, and the last owner always stays."""
	problems = []
	if not can(actor_role, "manage_team"):
		problems.append("Only an owner or admin manages the team")
	if (target_role == OWNER or new_role == OWNER) and actor_role != OWNER:
		problems.append("Only an owner adds or changes an owner")
	if target_role == OWNER and new_role != OWNER and owners <= 1:
		problems.append("The organisation keeps at least one owner")
	if new_role is not None and new_role not in ROLES:
		problems.append(f"No role {new_role}")
	return problems


def token_hash(token: str, key: str) -> str:
	"""Invitation and verification tokens are stored hashed: a database read does not yield a usable link."""
	return hmac.new(key.encode(), token.encode(), hashlib.sha256).hexdigest()


def invitation_findings(status: str, expires_on: datetime.datetime, now: datetime.datetime, invited_email: str,
		user_email: str) -> list[str]:
	if status != "Pending":
		return [f"The invitation is {status.lower()}"]
	if now > expires_on:
		return ["The invitation has expired; ask for a new one"]
	if (invited_email or "").strip().lower() != (user_email or "").strip().lower():
		return ["The invitation was sent to another email address"]
	return []

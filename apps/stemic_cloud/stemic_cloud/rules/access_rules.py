"""Platform staff never see a tenant's insurance data by default. Access is asked with a reason and a scope, approved
by the organisation's owner or admin, and ends by itself."""

import datetime

MAX_HOURS = 72
SCOPES = ("Read Only", "Support (Read and Write)")


def grant_findings(reason: str, hours, scope: str) -> list[str]:
	problems = []
	if len((reason or "").strip()) < 10:
		problems.append("Say why access is needed (the ticket or the problem)")
	try:
		h = int(hours)
	except (TypeError, ValueError):
		h = 0
	if not 1 <= h <= MAX_HOURS:
		problems.append(f"Access lasts from 1 to {MAX_HOURS} hours")
	if scope not in SCOPES:
		problems.append("Choose the scope")
	return problems


def active(status: str, valid_from: datetime.datetime | None, valid_until: datetime.datetime | None,
		now: datetime.datetime) -> bool:
	return status == "Approved" and bool(valid_from) and bool(valid_until) and valid_from <= now <= valid_until


def expired(status: str, valid_until: datetime.datetime | None, now: datetime.datetime) -> bool:
	return status == "Approved" and valid_until is not None and now > valid_until

"""Subscriptions and their invoices, without Frappe. A missed payment never cuts an insurer off at once: past due,
then a grace period with reminders, and only then suspension, which a platform finance user confirms."""

import datetime
from decimal import ROUND_HALF_UP, Decimal

TRIAL, ACTIVE, PAST_DUE, GRACE, SUSPENDED, CANCELLED = "Trial", "Active", "Past Due", "Grace", "Suspended", "Cancelled"
CYCLE_MONTHS = {"Monthly": 1, "Annual": 12}


def add_months(day: datetime.date, months: int) -> datetime.date:
	month = day.month - 1 + months
	year = day.year + month // 12
	month = month % 12 + 1
	last = [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30,
		31][month - 1]
	return datetime.date(year, month, min(day.day, last))


def period_end(start: datetime.date, cycle: str) -> datetime.date:
	"""The last day covered by a period that starts on `start`."""
	return add_months(start, CYCLE_MONTHS[cycle]) - datetime.timedelta(days=1)


def invoice_amount(monthly_price, annual_price, cycle: str) -> Decimal:
	"""What one period costs: the annual price when the plan has one, else twelve months."""
	monthly = Decimal(str(monthly_price or 0))
	if cycle == "Annual":
		annual = Decimal(str(annual_price or 0)) or monthly * 12
		return annual.quantize(Decimal("0.01"), ROUND_HALF_UP)
	return monthly.quantize(Decimal("0.01"), ROUND_HALF_UP)


def next_status(status: str, today: datetime.date, trial_ends: datetime.date | None,
		oldest_unpaid_due: datetime.date | None, grace_days: int) -> str:
	"""Where a subscription stands today. Suspension is proposed (the status reads Grace until a person confirms
	Suspended); a cancelled or suspended subscription stays as it is."""
	if status in (CANCELLED, SUSPENDED):
		return status
	if status == TRIAL and trial_ends and today <= trial_ends:
		return TRIAL
	if oldest_unpaid_due is None or today <= oldest_unpaid_due:
		return ACTIVE
	if (today - oldest_unpaid_due).days <= grace_days:
		return PAST_DUE if (today - oldest_unpaid_due).days <= 3 else GRACE
	return GRACE


def suspension_due(today: datetime.date, oldest_unpaid_due: datetime.date | None, grace_days: int) -> bool:
	"""The grace period is over: a platform finance user may suspend (read-only access to the ERP stays)."""
	return oldest_unpaid_due is not None and (today - oldest_unpaid_due).days > grace_days


def seat_findings(max_users: int | None, active_users: int) -> list[str]:
	if max_users and active_users > max_users:
		return [f"{active_users} users are active and the plan allows {max_users}"]
	return []


def plan_change_findings(current_price, new_price, active_users: int, new_max_users: int | None) -> list[str]:
	"""A downgrade must fit the users already active."""
	problems = seat_findings(new_max_users, active_users)
	if problems:
		return [f"Too many users for that plan: {problems[0]}; remove users first"]
	return []

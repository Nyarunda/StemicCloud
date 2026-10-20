"""Subscriptions: a trial, then one invoice per period. Phase 1 records payments by hand (Platform Finance marks an
invoice paid with its reference); M-Pesa and card collection come in phase 2.

An unpaid invoice moves the subscription to Past Due, then Grace, with reminders to the billing contacts; when the
grace period is over, Platform Finance is asked to decide, and only a person suspends. Suspension leaves the ERP
readable (maintenance mode with reads), so an insurer never loses sight of its policies; paying resumes it."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime, today

from stemic_cloud.audit import log
from stemic_cloud.rules import subscription_rules as R

FINANCE = "Platform Finance"


def _settings():
	return frappe.get_cached_doc("Cloud Settings")


def start_subscription(organization, plan, cycle="Monthly"):
	p = frappe.get_doc("Subscription Plan", plan)
	days = cint(p.trial_days or _settings().trial_days or 0)
	start = getdate(today())
	sub = frappe.get_doc({"doctype": "Cloud Subscription", "organization": organization, "plan": plan,
		"billing_cycle": cycle, "start_date": start, "currency": p.currency,
		"trial_ends_on": add_days(start, days - 1) if days else None, "status": "Trial" if days else "Active"})
	sub.flags.ignore_permissions = True
	sub.insert()
	if not days:
		issue_invoice(sub, start)
	log("Subscription started", organization=organization, reference=("Cloud Subscription", sub.name),
		details={"plan": plan, "cycle": cycle, "trial_days": days})
	return sub.name


def issue_invoice(sub, period_start):
	p = frappe.get_doc("Subscription Plan", sub.plan)
	end = R.period_end(getdate(period_start), sub.billing_cycle)
	inv = frappe.get_doc({"doctype": "Subscription Invoice", "subscription": sub.name, "organization":
		sub.organization, "plan": sub.plan, "currency": p.currency, "period_start": period_start, "period_end": end,
		"amount": R.invoice_amount(p.monthly_price, p.annual_price, sub.billing_cycle),
		"due_date": add_days(period_start, cint(_settings().invoice_due_days or 7)), "status": "Issued"})
	inv.insert(ignore_permissions=True)
	sub.db_set({"current_period_start": period_start, "current_period_end": end})
	_tell_billing(sub.organization, _("Invoice {0} for {1} {2}").format(inv.name, inv.currency, inv.amount),
		_("Your Stemic Insurance invoice {0} for {1} to {2} is due on {3}.").format(inv.name, period_start, end,
		inv.due_date))
	log("Invoice issued", organization=sub.organization, reference=("Subscription Invoice", inv.name),
		actor="Administrator")
	return inv.name


def _tell_billing(organization, subject, message):
	users = frappe.get_all("Organization Member", filters={"organization": organization, "status": "Active",
		"role": ["in", ["Owner", "Billing Admin"]]}, pluck="user")
	emails = [frappe.db.get_value("User", u, "email") for u in users]
	if emails:
		frappe.sendmail(recipients=[e for e in emails if e], subject=subject, message=message)


def oldest_unpaid_due(subscription):
	return frappe.db.get_value("Subscription Invoice", {"subscription": subscription, "status": "Issued"},
		"due_date", order_by="due_date asc")


def daily():
	"""Invoices for the periods that start, and each subscription's standing."""
	t = getdate(today())
	grace = cint(_settings().grace_days or 14)
	for name in frappe.get_all("Cloud Subscription", filters={"status": ["not in", ["Cancelled"]]}, pluck="name"):
		try:
			sub = frappe.get_doc("Cloud Subscription", name)
			if sub.status == "Trial" and sub.trial_ends_on and t > getdate(sub.trial_ends_on):
				issue_invoice(sub, add_days(sub.trial_ends_on, 1))
			elif sub.status != "Suspended" and sub.current_period_end and t > getdate(sub.current_period_end):
				issue_invoice(sub, add_days(sub.current_period_end, 1))
			due = oldest_unpaid_due(sub.name)
			new = R.next_status(sub.status, t, getdate(sub.trial_ends_on) if sub.trial_ends_on else None,
				getdate(due) if due else None, grace)
			if new != sub.status:
				sub.db_set("status", new)
				log(f"Subscription {new}", organization=sub.organization, reference=("Cloud Subscription", sub.name),
					actor="Administrator")
				if new in ("Past Due", "Grace"):
					_tell_billing(sub.organization, _("Your Stemic Insurance subscription is {0}").format(_(new)),
						_("An invoice is unpaid since {0}. Your ERP keeps working during the grace period of {1} days."
						).format(due, grace))
			if due and R.suspension_due(t, getdate(due), grace) and not frappe.db.exists("ToDo", {
					"reference_type": "Cloud Subscription", "reference_name": sub.name, "status": "Open"}):
				_ask_finance(sub, due)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Stemic Cloud: subscription {name}")


def _ask_finance(sub, due):
	from frappe.desk.form.assign_to import add

	users = [u for u in frappe.get_all("Has Role", filters={"role": FINANCE, "parenttype": "User"}, pluck="parent")
		if frappe.db.get_value("User", u, "enabled")]
	if users:
		add({"doctype": "Cloud Subscription", "name": sub.name, "assign_to": users[:1], "description": _(
			"Grace period over: an invoice due {0} is unpaid. Decide whether to suspend (the ERP stays readable)."
		).format(due)})


def _require_finance():
	if not set(frappe.get_roles()) & {FINANCE, "Platform Super Admin", "System Manager"}:
		frappe.throw(_("Needs the role {0}").format(FINANCE), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def mark_paid(invoice, reference, paid_on=None):
	_require_finance()
	inv = frappe.get_doc("Subscription Invoice", invoice)
	if inv.status != "Issued":
		frappe.throw(_("Invoice {0} is {1}").format(inv.name, _(inv.status)))
	if not (reference or "").strip():
		frappe.throw(_("Give the payment reference"))
	inv.db_set({"status": "Paid", "paid_on": paid_on or today(), "payment_reference": reference.strip(),
		"recorded_by": frappe.session.user})
	log("Invoice paid", organization=inv.organization, reference=("Subscription Invoice", inv.name),
		details={"reference": reference})
	sub = frappe.get_doc("Cloud Subscription", inv.subscription)
	if not oldest_unpaid_due(sub.name) and sub.status in ("Past Due", "Grace", "Suspended"):
		if sub.status == "Suspended":
			_resume_tenants(sub.organization)
		sub.db_set({"status": "Active", "suspended_by": None, "suspended_on": None})
		log("Subscription Active", organization=sub.organization, reference=("Cloud Subscription", sub.name))


@frappe.whitelist(methods=["POST"])
def void_invoice(invoice, reason):
	_require_finance()
	inv = frappe.get_doc("Subscription Invoice", invoice)
	if inv.status != "Issued" or not (reason or "").strip():
		frappe.throw(_("Only an unpaid invoice is voided, with a reason"))
	inv.db_set("status", "Void")
	log("Invoice voided", organization=inv.organization, reference=("Subscription Invoice", inv.name),
		details={"reason": reason})


@frappe.whitelist(methods=["POST"])
def suspend(subscription, reason):
	"""Platform Finance, after the grace period: the ERP becomes read-only."""
	_require_finance()
	sub = frappe.get_doc("Cloud Subscription", subscription)
	due = oldest_unpaid_due(sub.name)
	if not due or not R.suspension_due(getdate(today()), getdate(due), cint(_settings().grace_days or 14)):
		frappe.throw(_("The grace period is not over"))
	if not (reason or "").strip():
		frappe.throw(_("Give the reason"))
	from stemic_cloud.provisioning import set_read_only

	for t in frappe.get_all("Tenant", filters={"organization": sub.organization, "status": "Active"}, pluck="name"):
		set_read_only(t, True)
	sub.db_set({"status": "Suspended", "suspended_by": frappe.session.user, "suspended_on": now_datetime()})
	_tell_billing(sub.organization, _("Your Stemic Insurance ERP is read-only"), _("Your subscription is suspended "
		"for an unpaid invoice due {0}. You can still read your records; paying the invoice restores full use.").format(
		due))
	log("Subscription Suspended", organization=sub.organization, reference=("Cloud Subscription", sub.name),
		details={"reason": reason})


def _resume_tenants(organization):
	from stemic_cloud.provisioning import set_read_only

	for t in frappe.get_all("Tenant", filters={"organization": organization, "read_only": 1}, pluck="name"):
		set_read_only(t, False)


@frappe.whitelist(methods=["POST"])
def change_plan(organization, plan, billing_cycle=None):
	"""The owner changes plan; it applies from the next invoice, and a smaller plan must fit the active users."""
	from stemic_cloud.accounts import require

	require(organization, "change_plan")
	sub = frappe.get_doc("Cloud Subscription", {"organization": organization, "status": ["!=", "Cancelled"]})
	p = frappe.get_doc("Subscription Plan", plan)
	if not p.enabled or p.contact_sales:
		frappe.throw(_("That plan is not offered here"))
	problems = R.plan_change_findings(None, None, cint(sub.active_users), cint(p.max_users) or None)
	if problems:
		frappe.throw(_(problems[0]))
	old = sub.plan
	sub.db_set({"plan": plan, "billing_cycle": billing_cycle or sub.billing_cycle})
	log("Plan changed", organization=organization, reference=("Cloud Subscription", sub.name),
		details={"from": old, "to": plan, "cycle": billing_cycle or sub.billing_cycle})


@frappe.whitelist(methods=["POST"])
def cancel(organization, reason):
	"""The owner cancels: no further invoices. The tenant is kept until the data export and termination are agreed
	(support handles them in phase 1)."""
	from stemic_cloud.accounts import require

	require(organization, "cancel")
	if not (reason or "").strip():
		frappe.throw(_("Tell us why"))
	sub = frappe.get_doc("Cloud Subscription", {"organization": organization, "status": ["!=", "Cancelled"]})
	sub.db_set({"status": "Cancelled", "cancelled_on": today(), "cancel_reason": reason.strip()})
	log("Subscription Cancelled", organization=organization, reference=("Cloud Subscription", sub.name),
		details={"reason": reason})
	support = _settings().support_email
	if support:
		frappe.sendmail(recipients=[support], subject=_("Cancellation: {0}").format(organization), message=reason)

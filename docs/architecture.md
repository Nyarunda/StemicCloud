# Architecture

## Pieces

```
app.stemicinsurance.com  (control-plane site, app stemic_cloud)
 ├─ /register, /register/verify      registration and email verification (guests, rate-limited)
 ├─ /cloud/...                        customer portal (role Cloud Customer, no desk)
 ├─ /desk/stemic-cloud                platform desk (Platform Super Admin, Support, Finance)
 └─ background jobs                   provisioning (long queue), daily billing and health, hourly access expiry
          │  bench <fixed argv>  (no shell, timeout, secrets masked)
          ▼
 Deployment Group: a bench folder on a server  ──►  acme.stemicinsurance.com   (site: erpnext + insurance)
                                                ──►  bima.stemicinsurance.com   ...
```

The control plane holds no insurance data. A tenant's policies, customers and accounts live only in its own site and
database. The control plane knows a tenant's address, status, health, user count and app version, which it reads with
`bench` commands that return a number or a version, never records.

## Registration to a running ERP

1. **Register** (`accounts.register`): checks the form (subdomain rules in `rules/naming_rules.py`, plan, terms),
   stores a Cloud Registration with the token hashed (HMAC SHA-256 with the site's encryption key) and emails the
   link. The answer is the same whether the email is known or not; a known address gets an email telling them to log
   in instead.
2. **Verify** (`accounts.verify`, from `/register/verify?token=`): the link works once and for
   `verification_hours`. It creates the User (role Cloud Customer, website user), the Cloud Organization, the
   Owner membership, the subscription (a trial when the plan or settings give trial days, otherwise the first invoice)
   and the Tenant, and queues the provisioning job. The person goes to Frappe's own set-password page and from there
   to `/cloud`.
3. **Provision** (`provisioning.run_job`): the steps of `rules/provisioning_rules.plan`, each recorded on the Tenant
   Provisioning Job with its command (secrets as `***`), output and times:
   reserve → `new-site` → `install-app` for each app of the group → `migrate` → `set-config host_name` → insurance
   business type → `add-user` (the registrant, System Manager and Insurance Administrator) → `enable-scheduler` →
   `backup` (optional) → `setup nginx` (optional) → health (`/api/method/ping`) → set-password email on the tenant
   (optional) → activate. A failure stops the job, marks the tenant Failed, assigns it to Platform Support; Retry
   continues from the failed step. Optional steps that fail are Skipped.
4. **Active**: the owner is emailed the address. The tenant's Administrator password is random and never stored, so
   nobody at Stemic holds a login on the tenant.

## Subscriptions

```
Trial ──(trial ends, invoice issued)──► Active ──(invoice unpaid after due)──► Past Due (days 1-3)
                                          ▲                                       │
                                          │ paid                                   ▼
                                          └──────────────── Grace (to grace_days) ──► Platform Finance asked (ToDo)
                                                                                         │ decides
                                                                                         ▼
                                                     Suspended: ERP read-only (maintenance mode, reads allowed)
Cancelled: by the owner; no more invoices; the tenant is kept until export and termination are agreed.
```

`rules/subscription_rules.py` holds the dates, amounts and transitions; `subscriptions.daily` applies them. Payment is
recorded by hand in Phase 1 (Mark Paid with the reference); paying the last unpaid invoice of a suspended subscription
takes the ERP out of read-only.

## Who may do what

Organisation roles (portal only; they give nothing in the ERP, whose own users and roles apply there):

| Action | Owner | Admin | Billing Admin | Member |
|---|:-:|:-:|:-:|:-:|
| See the dashboard and My ERP | ✓ | ✓ | ✓ | ✓ |
| See billing and invoices | ✓ | ✓ | ✓ | |
| Change plan, cancel, request a data export | ✓ | | | |
| Invite, change and remove members | ✓ | ✓ | | |
| Onboarding checklist | ✓ | ✓ | | |
| Approve or end Stemic access to the ERP | ✓ | ✓ | | |

An organisation always keeps an owner; an admin cannot make or remove owners (`rules/membership_rules.py`).

Platform roles (desk): Platform Super Admin (everything on the control plane), Platform Support (organisations,
tenants, jobs; asks for access), Platform Finance (plans, subscriptions, invoices; suspends). These roles require
two-factor login once it is turned on in System Settings. None of them opens a tenant.

## Access to a tenant's data

A Tenant Access Grant is the only way in. Platform Support asks on the Tenant form with a reason (at least a ticket or
the problem), a scope (Read Only → the tenant role Report Manager; Support → System Manager) and 1-72 hours. The
organisation's owners and admins are emailed and decide on `/cloud/security`. Approval runs `add-user` on the tenant
for a login of the form `name+acc-00001@domain`, so every grant is a separate, traceable user; the hourly job disables
it when the time is up, and either side can end it earlier. Each step is in the audit log.

## Audit and login monitoring

`audit.log` writes a Cloud Audit Log row for registration, verification, invitations, role changes, plan changes,
invoices, payments, suspension, provisioning, access requests and decisions, data-export requests and session
revocations. The row cannot be edited or deleted. `security.on_login` writes unusual logins (a network not seen in six
months, outside hours) and emails the alert user. Lockout after failed attempts, password strength and two-factor
login are Frappe's own.

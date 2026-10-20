# Feature map

Each part of the Stemic Cloud specification, what Phase 1 (the MVP) built, where, and what it did not. "Frappe" means
the feature is Frappe's own and is used as it is.

## Not run

Nothing here has run on a Frappe site: there was no bench or MariaDB where it was written. What was run: the rules'
unit tests, the import of every module against a stand-in for Frappe, ruff, the Jinja templates' parse, the form
scripts' syntax, and the generators. The first install on a site, the portal pages, the emails, and a provisioning job
on a real bench are untested. Try the whole flow with the "Dry Run" deployment group first (it records each command
without running it), then one real tenant.

## Authentication and security

| Spec | Built | Where |
|---|---|---|
| Email and password login, password reset | Frappe | `/login`, `/update-password` |
| Email verification before an organisation exists | ✓ | `accounts.register`, `accounts.verify`, `/register/verify` |
| Rate limits on registration | ✓ 5 an hour per address | `accounts.register` |
| Lockout after failed logins, password strength | Frappe, defaults set at install | `setup/install.py` |
| MFA | Frappe two-factor; platform roles marked for it | System Settings must turn it on (`docs/setup.md`) |
| Sessions: see, sign out others | ✓ count and "sign out other sessions"; Platform Super Admin revokes a person's sessions | `/cloud/security`, `admin.revoke_sessions` |
| Login history | Frappe Activity Log, shown on the portal | `/cloud/security` |
| Unusual login alerts | ✓ new network, to the audit log and the alert user | `security.on_login` |
| Tokens never stored in clear | ✓ HMAC SHA-256 | `rules/membership_rules.token_hash` |
| Social login, SSO / SAML | not built | Frappe's Social Login Keys can be configured; not tested |

## Roles

| Spec | Built |
|---|---|
| Platform Super Admin, Support, Finance | ✓ desk roles with per-doctype permissions (`tools/build_doctypes.py`) |
| Organisation Owner, Admin, Billing Admin, Member | ✓ `rules/membership_rules.ALLOWED`; separate from ERP roles |
| No automatic platform access to tenant data | ✓ Tenant Access Grant (reason, scope, 1-72 h, approval, auto-expiry, audit) |
| Platform Sales, Platform Engineer roles | not built (Super Admin and Support cover them in Phase 1) |

## Company registration

| Spec | Built |
|---|---|
| Company details, type, registration number, country, currency, time zone | ✓ Cloud Registration → Cloud Organization |
| Subdomain with live availability check and reserved names | ✓ `rules/naming_rules.py`, `accounts.check_subdomain` |
| Plan and billing cycle chosen at registration | ✓ |
| Terms accepted, version, time and address recorded | ✓ on the organisation |
| KYC documents (licence, certificate) uploaded and reviewed | not built |
| Company approval by Stemic before provisioning | not built: verification of the email provisions straight away |
| One person registering a second organisation | not built: a registered email is told to log in; add them by invitation instead |

## Tenant provisioning

| Spec | Built |
|---|---|
| Site, database, apps, migrations, host name, business type, administrator, scheduler, backup, nginx, health check, activation | ✓ `rules/provisioning_rules.plan`, `provisioning.run_job` |
| Each step logged with command, output and time; secrets masked | ✓ Tenant Provisioning Job |
| Retry from the failed step | ✓ |
| Platform Support told of a failure | ✓ assignment (ToDo) |
| Deployment groups, a default for new tenants, Dry Run | ✓ Deployment Group |
| Commands on another server (SSH or an agent) | not built: Phase 1 runs the bench on the same server |
| Choosing a region or a dedicated server | not built |
| A separate database server per group | not built (the bench's MariaDB) |
| Custom domains for a tenant | not built |
| DNS records per tenant | not needed: wildcard DNS (`docs/setup.md`) |

## Subscriptions and billing

| Spec | Built |
|---|---|
| Plans with prices, users, features, trial | ✓ Subscription Plan (Starter, Business, Enterprise samples) |
| Trial, Active, Past Due, Grace, Suspended, Cancelled | ✓ `rules/subscription_rules.next_status`, `subscriptions.daily` |
| An invoice per period, reminders | ✓ Subscription Invoice, emails to Owner and Billing Admins |
| Suspension after grace | ✓ by Platform Finance only; the ERP stays readable |
| Payments recorded | ✓ by hand (Mark Paid with reference) |
| Change plan, cancel | ✓ by the owner; a smaller plan must fit the active users; applies from the next invoice |
| Seats over the plan | ✓ counted daily on the tenant and shown; not enforced in the ERP |
| M-Pesa (STK push), cards, automatic collection | not built. The insurance app's M-Pesa connector is the model for Phase 2 |
| Proration on a plan change mid-period | not built |
| Invoices as PDF, taxes (VAT) on invoices, ERPNext accounting of the platform's revenue | not built |
| Coupons and discounts | not built |

## Customer dashboard and ERP environment

| Spec | Built |
|---|---|
| Open the ERP, status, health, version, users, subscription, unpaid invoices, onboarding, recent activity | ✓ `/cloud` |
| Environment details and provisioning steps | ✓ `/cloud/erp` |
| Request a data export | ✓ a request to support (support prepares it by hand) |
| Self-service backups and restores, staging copies, upgrades on request | not built |
| Usage charts (storage, API calls) | not built |

## Team, onboarding, support

| Spec | Built |
|---|---|
| Invitations with a role, accept, revoke, change role, remove; the last owner stays | ✓ `/cloud/team`, `accounts.py` |
| Onboarding checklist with links into the tenant ERP and progress | ✓ `/cloud/onboarding` (ticked by hand; not read from the ERP) |
| Support tickets | not built: a support email address. Frappe Helpdesk is the candidate for Phase 2 |
| Knowledge base, status page, announcements | not built |

## Platform administration

| Spec | Built |
|---|---|
| Workspace with organisations, subscriptions, trials, past due, suspended, tenants, alerts, failed jobs, outstanding, MRR | ✓ `tools/build_navigation.py` |
| Audit log of administrative and customer actions, append-only | ✓ Cloud Audit Log |
| Impersonating a customer on the portal | not built, on purpose |
| Bulk upgrades of tenants | not built: `bench --site all migrate` by hand |

## Database architecture, GitHub and DigitalOcean

One database per tenant (a Frappe site each), the control plane's own database for platform data: as the spec asks.
CI on GitHub runs the checks above. DigitalOcean is described in `docs/setup.md`; no Terraform, no droplet automation.

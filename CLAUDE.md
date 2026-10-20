# Stemic Cloud: how features are built

Stemic Cloud is the SaaS control plane for the Stemic Insurance ERP (`Nyarunda/Insurance`). It is a Frappe app on its
own site; each customer's ERP is a separate Frappe site. The specification is the "Stemic Cloud" SaaS document; Phase 1
(the MVP) is what is built, and `docs/feature-map.md` maps each part of the specification to what exists.

## Use Frappe; do not duplicate it

1. **Frappe already has it** (users, login, password reset, two-factor login, lockout, sessions, Activity Log,
   email, background jobs, scheduler, roles and permissions): use it. The portal adds organisation roles on top.
2. **Frappe has nothing for it** (organisations, plans, subscriptions, invoices, tenants, provisioning, access
   grants, audit log): a doctype in `apps/stemic_cloud`, written by `tools/build_doctypes.py`.
3. **It cannot be done here safely:** do not fake it. Say so in `docs/feature-map.md`.

## Rules that do not bend

- Platform staff get no access to a tenant's data by default. Access is a Tenant Access Grant: asked with a reason and
  a scope, approved by the organisation's owner or admin, time-limited, logged, and ended by the hourly job.
- Tenants never get a shell, database access or arbitrary commands. The control plane runs `bench` with a fixed list
  of arguments it builds itself (`rules/provisioning_rules.py`), never through a shell, with secrets passed separately
  and masked in logs.
- Suspension is a person's decision (Platform Finance) after the grace period, and keeps the ERP readable.
- Every administrative and customer action goes to the Cloud Audit Log, which is never changed or deleted.
- Fields the platform's code owns (statuses, decisions, the tenant's state) are written with `db_set` by that code;
  `stemic_cloud/guards.py` refuses them in an ordinary save.

## Working rules

- Change doctypes in `apps/stemic_cloud/tools/build_doctypes.py` and run it (and `build_navigation.py`); CI fails when
  the generated JSON is not committed.
- Patches in `apps/stemic_cloud/stemic_cloud/patches.txt` are append-only once anyone may have run them.
- Pure rules (naming, subscriptions, membership, access, provisioning plan, onboarding) live in
  `stemic_cloud/rules/` with unit tests that run without a site:
  `cd apps/stemic_cloud && python3 -I -m unittest discover -s tests`.
- Say plainly in the docs and the commit what was not built or not run.

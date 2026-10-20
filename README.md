# Stemic Cloud

The control plane behind **app.stemicinsurance.com**: an insurance company registers, confirms its email, picks a plan,
and gets its own Stemic Insurance ERP (ERPNext with the `insurance` app from `Nyarunda/Insurance`) at
`{subdomain}.stemicinsurance.com`. The same site bills the subscription, lets the company manage its portal team and
onboarding, and gives platform staff an administration desk, without giving them the companies' insurance data.

It is one Frappe app, `apps/stemic_cloud`, installed on its own site. Each customer ERP is a separate Frappe site on a
bench the control plane drives with `bench` commands.

| | |
|---|---|
| Customer portal | `/register`, `/register/verify`, `/cloud` (dashboard, My ERP, billing, team, onboarding, security) |
| Platform desk | `/desk/stemic-cloud`: organisations, subscriptions, invoices, tenants, provisioning jobs, access grants, audit |
| Tenants | one Frappe site each, created by a background job (`stemic_cloud/provisioning.py`) |

## Versions

| Component | Version |
|---|---|
| Frappe (control plane and tenants) | v16 (tested against the code of 16.52) |
| ERPNext (tenants) | v16 (16.51) |
| insurance app (tenants) | `Nyarunda/Insurance` |
| Python | 3.14 |

## Documents

- `docs/architecture.md`: how the pieces fit, the states, the security model.
- `docs/setup.md`: a control-plane server, wildcard DNS and TLS, a bench for tenants, DigitalOcean.
- `docs/feature-map.md`: each part of the specification, what was built, what was not.
- `CLAUDE.md`: how features are added here.

## Checks

```
cd apps/stemic_cloud
python3 -I -m unittest discover -s tests          # the rules, no site needed
python3 -I tests/standin/import_check.py          # every module imports
python3 -I tools/build_doctypes.py && python3 -I tools/build_navigation.py   # regenerate, then commit the JSON
```

Nothing here has been run on a Frappe site yet: see "Not run" in `docs/feature-map.md`.

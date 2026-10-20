# Setting up

Phase 1 runs the control plane and the tenants' bench on one server. The control plane drives that bench with `bench`
commands, so it runs as the same Unix user (usually `frappe`).

## 1. Server

A DigitalOcean droplet (Ubuntu 24.04, at least 8 GB RAM for a handful of tenants; ERPNext sites take ~1 GB of RAM
under load each), with a Managed or local MariaDB 11 and Redis. Install Frappe Bench in the usual way
(`pip install frappe-bench`, `bench init --frappe-branch version-16 frappe-bench`).

```
cd ~/frappe-bench
bench get-app erpnext --branch version-16
bench get-app https://github.com/Nyarunda/Insurance --branch <release>      # the tenants' app (apps/insurance)
bench get-app https://github.com/Nyarunda/StemicCloud                       # this repository (apps/stemic_cloud)
bench new-site app.stemicinsurance.com --db-root-password ... --admin-password ...
bench --site app.stemicinsurance.com install-app stemic_cloud
bench --site app.stemicinsurance.com enable-scheduler
bench setup production frappe      # supervisor and nginx
```

Both repositories keep their app one folder down (`apps/insurance`, `apps/stemic_cloud`); point `bench get-app` at a
checkout and symlink the app folder into `frappe-bench/apps` if your bench version does not accept a sub-folder.

Do not install `erpnext` or `insurance` on the control-plane site: it holds no insurance data.

## 2. DNS and TLS

- `app.stemicinsurance.com` → the server.
- `*.stemicinsurance.com` → the server (a wildcard A record), so a new tenant answers without a DNS change.
- A wildcard certificate for `*.stemicinsurance.com` (Let's Encrypt with the DNS-01 challenge, e.g. certbot with the
  DigitalOcean DNS plugin), configured once in nginx. `bench setup nginx` after each site (the job's optional "web"
  step) keeps the server blocks current.

## 3. Cloud Settings (desk → Stemic Cloud → Settings)

Root domain, portal address, support email, terms version and address, trial and grace days, invoice due days, link
validity, and the user who receives security alerts. Configure outgoing email (Email Account) first: registration,
invitations and reminders are emails.

## 4. Deployment Group

Install creates a group "Dry Run" that records each command without running it, so the whole portal can be tried
first. For real tenants, make a group with:

- Runs Commands: Local Bench; Bench Folder: `/home/frappe/frappe-bench`;
- MariaDB Root Password (stored encrypted, passed to `new-site` and never logged);
- Apps on Each Site: `erpnext` then `insurance`;
- Health Check Through: `http://127.0.0.1` when the server cannot reach itself on its public name (the site goes as
  the Host header);
- Default for New Tenants, and turn the Dry Run group's default off.

The background worker for the `long` queue must be running (`bench worker --queue long` under supervisor, which
`bench setup production` configures).

## 5. Each tenant's email

The administrator's set-password email is sent by the tenant site. Give each tenant an outgoing Email Account (or a
default one in `common_site_config.json`); otherwise the job's "invite" step is Skipped and the administrator uses
"Forgot password" on the tenant.

## 6. Two-factor login for platform staff

The platform roles are marked for two-factor login. Turn it on in System Settings (Enable Two Factor Auth, method
OTP App or Email) once the platform staff can receive codes.

## 7. Backups

The job takes a first backup of each tenant. Schedule `bench --site all backup --with-files` (or DigitalOcean volume
snapshots) and copy the backups off the server; restoring is by hand in Phase 1.

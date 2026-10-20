app_name = "stemic_cloud"
app_title = "Stemic Cloud"
app_publisher = "Nyarunda"
app_description = "The control plane: registration, organisations, plans and billing, tenant provisioning, the portal"
app_email = ""
app_license = "proprietary"

app_home = "/desk/stemic-cloud"
add_to_apps_screen = [{"name": app_name, "title": app_title, "route": app_home}]

# Roles, the security defaults, sample plans and a Dry Run deployment group (stemic_cloud/setup/install.py).
after_install = "stemic_cloud.setup.install.after_install"
after_migrate = "stemic_cloud.setup.install.after_migrate"

# The customer portal is /cloud; customers land there after logging in.
role_home_page = {"Cloud Customer": "cloud"}

scheduler_events = {
	# Invoices for periods that start, Past Due / Grace / the suspension question (subscriptions); tenant health,
	# usage against the plan and app version (provisioning).
	"daily": ["stemic_cloud.subscriptions.daily", "stemic_cloud.provisioning.daily"],
	# Platform access to a tenant ends on time.
	"hourly": ["stemic_cloud.admin.hourly"],
}

# Unusual logins go to the audit log and the alert user; the login is never blocked.
on_login = "stemic_cloud.security.on_login"

doctype_js = {
	"Subscription Invoice": "public/js/subscription_invoice.js",
	"Cloud Subscription": "public/js/cloud_subscription.js",
	"Tenant Provisioning Job": "public/js/tenant_provisioning_job.js",
	"Tenant": "public/js/tenant.js",
	"Tenant Access Grant": "public/js/tenant_access_grant.js",
}

"""The onboarding checklist after provisioning. Each step opens the tenant's own screen: the portal tracks completion,
it never holds the insurance set-up itself."""

STEPS = [
	("company", "Confirm company information", "/app/company"),
	("branches", "Configure branches", "/app/branch"),
	("staff", "Add staff", "/app/user"),
	("products", "Configure insurance products", "/app/insurance-product"),
	("underwriters", "Configure underwriters", "/app/supplier?ins_is_insurer=1"),
	("payments", "Configure payment methods", "/app/mode-of-payment"),
	("messaging", "Configure email and SMS", "/app/email-account"),
	("complete", "Complete set-up", "/desk/insurance"),
]


def checklist(done: set[str], base_url: str) -> list[dict]:
	return [{"code": c, "title": t, "url": base_url.rstrip("/") + path, "done": c in done} for c, t, path in STEPS]


def progress(done: set[str]) -> int:
	codes = {c for c, _t, _p in STEPS}
	return round(100 * len(done & codes) / len(codes))

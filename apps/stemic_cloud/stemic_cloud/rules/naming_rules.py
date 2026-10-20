"""Tenant names: a subdomain under the platform's root domain, chosen at registration."""

import re

SUBDOMAIN = re.compile(r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")
RESERVED = frozenset({
	"app", "admin", "api", "www", "mail", "smtp", "imap", "pop", "ftp", "ns1", "ns2", "status", "support", "help",
	"docs", "blog", "billing", "pay", "payments", "portal", "login", "auth", "sso", "cdn", "static", "assets",
	"files", "dev", "test", "staging", "demo", "stemic", "stemicinsurance", "root", "system", "internal",
})


def subdomain_findings(name: str) -> list[str]:
	"""Why a subdomain cannot be used (empty when it can): 3 to 32 letters, digits and hyphens, starting with a letter,
	no double hyphen, not a reserved name."""
	n = (name or "").strip().lower()
	if not SUBDOMAIN.match(n):
		return ["Use 3 to 32 lower-case letters, digits and hyphens, starting with a letter and not ending in a hyphen"]
	if "--" in n:
		return ["Do not use two hyphens together"]
	if n in RESERVED:
		return [f"{n} is reserved"]
	return []


def site_name(subdomain: str, root_domain: str) -> str:
	return f"{subdomain.strip().lower()}.{root_domain.strip().lower().strip('.')}"


def suggest(company_name: str) -> str:
	"""A subdomain from a company name: ABC Insurance Brokers Ltd -> abc-insurance-brokers."""
	words = re.findall(r"[a-z0-9]+", (company_name or "").lower())
	words = [w for w in words if w not in {"ltd", "limited", "plc", "llc", "inc", "co", "company", "the"}]
	text = "-".join(words)[:32].strip("-")
	if not text or not text[0].isalpha():
		text = ("t-" + text)[:32].strip("-")
	return text if len(text) >= 3 else (text + "-co")[:32]

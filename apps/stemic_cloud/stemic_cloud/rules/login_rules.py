"""Unusual logins on the platform (the same rule the insurance app uses): a network the user never logged in from,
or outside working hours."""

import datetime
import ipaddress

# ---- unusual logins (S7)


def network_of(ip: str) -> str | None:
	"""The network an address belongs to for comparing logins: /24 for IPv4, /48 for IPv6."""
	try:
		address = ipaddress.ip_address((ip or "").strip())
	except ValueError:
		return None
	prefix = 24 if address.version == 4 else 48
	return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))


def login_findings(ip: str, known_ips: list[str], at: datetime.datetime, hours: tuple | None,
		working_days=(0, 1, 2, 3, 4, 5)) -> list[str]:
	"""Why a login looks unusual: from a network the user never logged in from (when they have a history), or
	outside working hours or days. ``hours`` is (from, to) as times, or None."""
	reasons = []
	net = network_of(ip)
	known = {network_of(x) for x in known_ips if x}
	known.discard(None)
	if net and known and net not in known:
		reasons.append(f"a new network {net}")
	if hours:
		start, end = hours
		t = at.time()
		inside = start <= t <= end if start <= end else (t >= start or t <= end)
		if not inside:
			reasons.append(f"outside working hours ({start:%H:%M} to {end:%H:%M})")
	if at.weekday() not in working_days:
		reasons.append("on a day off")
	return reasons

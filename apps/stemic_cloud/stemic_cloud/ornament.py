"""The portal's seal: a guilloche rosette, the fine-line pattern of insurance certificates and security paper, drawn
as SVG paths (computed once). Pure; no Frappe."""

import functools
import math


def _curve(R, r, d, turns, steps, scale, cx, cy):
	pts = []
	k = (R - r) / r
	for i in range(steps + 1):
		t = 2 * math.pi * turns * i / steps
		x = (R - r) * math.cos(t) + d * math.cos(k * t)
		y = (R - r) * math.sin(t) - d * math.sin(k * t)
		pts.append((cx + x * scale, cy + y * scale))
	return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "Z"


@functools.lru_cache(maxsize=4)
def rosette(size: int = 200) -> tuple[str, ...]:
	"""Interleaved hypotrochoids (30, 12 and 18 lobes) and a fine outer band, in a size x size box."""
	c = size / 2
	return (
		_curve(90, 33, 62, 11, 3300, size / 325, c, c),   # 30 lobes, the body of the rosette
		_curve(96, 40, 50, 5, 1500, size / 308, c, c),    # 12 broad lobes over it
		_curve(54, 21, 26, 7, 1400, size / 262, c, c),    # 18 lobes round the centre
		_curve(120, 3, 4.5, 1, 2400, size / 252, c, c),   # the edge band, 40 fine lobes
	)

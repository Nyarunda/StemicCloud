"""Customer portal page (stemic_cloud/portal.py does the work)."""

from stemic_cloud import portal

no_cache = 1


def get_context(context):
	portal.security(context)
	return context

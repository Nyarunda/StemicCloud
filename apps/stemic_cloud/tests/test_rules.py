"""Stemic Cloud's pure rules."""

import datetime
import os
import sys
import unittest
from decimal import Decimal as D

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stemic_cloud.rules import access_rules as A  # noqa: E402
from stemic_cloud.rules import membership_rules as M  # noqa: E402
from stemic_cloud.rules import naming_rules as N  # noqa: E402
from stemic_cloud.rules import onboarding_rules as O  # noqa: E402
from stemic_cloud.rules import provisioning_rules as P  # noqa: E402
from stemic_cloud.rules import subscription_rules as S  # noqa: E402

d = datetime.date
dt = datetime.datetime


class TestNaming(unittest.TestCase):
	def test_subdomains(self):
		self.assertEqual(N.subdomain_findings("abc"), [])
		self.assertEqual(N.subdomain_findings("abc-brokers-2"), [])
		for bad in ("ab", "1abc", "abc-", "ABC!", "a" * 33, "", "a--b"):
			self.assertTrue(N.subdomain_findings(bad), bad)
		self.assertEqual(N.subdomain_findings("admin"), ["admin is reserved"])
		self.assertEqual(N.site_name("ABC", "stemicinsurance.com."), "abc.stemicinsurance.com")

	def test_suggest(self):
		self.assertEqual(N.suggest("ABC Insurance Brokers Ltd"), "abc-insurance-brokers")
		self.assertEqual(N.suggest("247 Cover Limited"), "t-247-cover")
		self.assertEqual(N.suggest("XY"), "xy-co")
		self.assertEqual(N.subdomain_findings(N.suggest("The Very Long Name of an Insurance Agency Company Ltd")), [])


class TestSubscriptions(unittest.TestCase):
	def test_periods(self):
		self.assertEqual(S.period_end(d(2026, 1, 31), "Monthly"), d(2026, 2, 27))
		self.assertEqual(S.period_end(d(2026, 3, 1), "Monthly"), d(2026, 3, 31))
		self.assertEqual(S.period_end(d(2026, 3, 1), "Annual"), d(2027, 2, 28))
		self.assertEqual(S.add_months(d(2028, 1, 31), 1), d(2028, 2, 29))

	def test_amounts(self):
		self.assertEqual(S.invoice_amount(29, None, "Monthly"), D("29.00"))
		self.assertEqual(S.invoice_amount(29, None, "Annual"), D("348.00"))
		self.assertEqual(S.invoice_amount(29, 290, "Annual"), D("290.00"))

	def test_status(self):
		t = d(2026, 10, 20)
		self.assertEqual(S.next_status("Trial", t, d(2026, 10, 30), None, 14), "Trial")
		self.assertEqual(S.next_status("Trial", t, d(2026, 10, 1), None, 14), "Active")
		self.assertEqual(S.next_status("Active", t, None, d(2026, 10, 19), 14), "Past Due")
		self.assertEqual(S.next_status("Active", t, None, d(2026, 10, 10), 14), "Grace")
		self.assertEqual(S.next_status("Grace", t, None, d(2026, 9, 1), 14), "Grace")
		self.assertEqual(S.next_status("Suspended", t, None, None, 14), "Suspended")
		self.assertTrue(S.suspension_due(t, d(2026, 9, 1), 14))
		self.assertFalse(S.suspension_due(t, d(2026, 10, 10), 14))

	def test_seats(self):
		self.assertEqual(S.seat_findings(3, 3), [])
		self.assertEqual(len(S.seat_findings(3, 4)), 1)
		self.assertEqual(len(S.plan_change_findings(99, 29, 8, 3)), 1)


class TestMembership(unittest.TestCase):
	def test_can(self):
		self.assertTrue(M.can("Billing Admin", "pay"))
		self.assertFalse(M.can("Billing Admin", "manage_erp"))
		self.assertFalse(M.can("Member", "view_billing"))
		self.assertFalse(M.can(None, "view"))

	def test_roles(self):
		self.assertEqual(M.role_change_findings("Owner", "Member", "Admin", 1), [])
		self.assertIn("at least one owner", M.role_change_findings("Owner", "Owner", None, 1)[0])
		self.assertEqual(M.role_change_findings("Owner", "Owner", None, 2), [])
		self.assertTrue(M.role_change_findings("Admin", "Owner", None, 2))
		self.assertTrue(M.role_change_findings("Member", "Member", None, 2))

	def test_tokens(self):
		self.assertEqual(M.token_hash("t", "k"), M.token_hash("t", "k"))
		self.assertNotEqual(M.token_hash("t", "k"), M.token_hash("t", "k2"))
		now = dt(2026, 10, 20, 10)
		self.assertEqual(M.invitation_findings("Pending", dt(2026, 10, 21), now, "A@x.com", "a@x.com"), [])
		self.assertTrue(M.invitation_findings("Pending", dt(2026, 10, 19), now, "a@x.com", "a@x.com"))
		self.assertTrue(M.invitation_findings("Pending", dt(2026, 10, 21), now, "a@x.com", "b@x.com"))
		self.assertTrue(M.invitation_findings("Accepted", dt(2026, 10, 21), now, "a@x.com", "a@x.com"))


class TestProvisioning(unittest.TestCase):
	def steps(self):
		return P.plan("abc.stemicinsurance.com", ["erpnext", "insurance"], "owner@abc.co.ke", "Jane", "Insurance Broker",
			"https://abc.stemicinsurance.com", "https://abc.stemicinsurance.com/api/method/ping")

	def test_plan(self):
		codes = [s.code for s in self.steps()]
		self.assertEqual(codes[:4], ["reserve", "new_site", "install_erpnext", "install_insurance"])
		self.assertEqual(codes[-1], "activate")
		self.assertIn("health", codes)
		bt = next(s for s in self.steps() if s.code == "business_type")
		self.assertIn('"value": "Broker"', bt.argv[-1])

	def test_secrets(self):
		new = next(s for s in self.steps() if s.code == "new_site")
		self.assertNotIn("pw", " ".join(P.shown(new.argv)))
		self.assertIn("***", P.shown(new.argv))
		run = P.filled(new.argv, {"db_root_password": "pw", "admin_password": "ad"})
		self.assertEqual(run[run.index("--db-root-password") + 1], "pw")
		with self.assertRaises(KeyError):
			P.filled(new.argv, {})

	def test_resume(self):
		left = P.resume_from(self.steps(), ["reserve", "new_site"])
		self.assertEqual(left[0].code, "install_erpnext")

	def test_email_safe(self):
		self.assertTrue(P.email_safe("jane.doe+x@abc.co.ke"))
		self.assertFalse(P.email_safe('a"b@x.com'))
		self.assertFalse(P.email_safe("a b@x.com"))


class TestAccessAndOnboarding(unittest.TestCase):
	def test_grants(self):
		self.assertEqual(A.grant_findings("Ticket 42: certificate fails", 4, "Read Only"), [])
		self.assertEqual(len(A.grant_findings("x", 100, "All")), 3)
		now = dt(2026, 10, 20, 12)
		self.assertTrue(A.active("Approved", dt(2026, 10, 20, 10), dt(2026, 10, 20, 14), now))
		self.assertFalse(A.active("Requested", dt(2026, 10, 20, 10), dt(2026, 10, 20, 14), now))
		self.assertTrue(A.expired("Approved", dt(2026, 10, 20, 11), now))

	def test_onboarding(self):
		items = O.checklist({"company", "staff"}, "https://abc.stemicinsurance.com/")
		self.assertEqual(items[0]["url"], "https://abc.stemicinsurance.com/app/company")
		self.assertEqual(O.progress({"company", "staff"}), 25)


class TestLogins(unittest.TestCase):
	def test_new_network(self):
		from stemic_cloud.rules.login_rules import login_findings

		at = dt(2026, 10, 19, 10)
		self.assertEqual(login_findings("41.90.12.9", ["41.90.12.7"], at, None), [])
		self.assertTrue(login_findings("102.1.1.1", ["41.90.12.7"], at, None))


class TestOrnament(unittest.TestCase):
	def test_rosette_paths_fit_the_box(self):
		import re

		from stemic_cloud.ornament import rosette

		paths = rosette(200)
		self.assertEqual(len(paths), 4)
		for d in paths:
			nums = [float(n) for n in re.findall(r"-?\d+\.\d+", d)]
			self.assertTrue(all(-1 <= n <= 201 for n in nums))

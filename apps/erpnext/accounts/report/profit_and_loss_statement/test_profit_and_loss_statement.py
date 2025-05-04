# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe.desk.query_report import export_query
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, today

from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.accounts.report.financial_statements import get_period_list
from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import execute
from erpnext.accounts.test.accounts_mixin import AccountsTestMixin


class TestProfitAndLossStatement(AccountsTestMixin, IntegrationTestCase):
	def setUp(self):
		self.create_company()
		self.create_customer()
		self.create_item()

	def tearDown(self):
		frappe.db.rollback()

	def create_sales_invoice(self, qty=1, rate=150, no_payment_schedule=False, do_not_submit=False):
		frappe.set_user("Administrator")
		si = create_sales_invoice(
			item=self.item,
			company=self.company,
			customer=self.customer,
			debit_to=self.debit_to,
			posting_date=today(),
			parent_cost_center=self.cost_center,
			cost_center=self.cost_center,
			rate=rate,
			price_list_rate=rate,
			qty=qty,
			do_not_save=1,
		)
		si = si.save()
		if not do_not_submit:
			si = si.submit()
		return si

	def get_fiscal_year(self):
		active_fy = frappe.db.get_all(
			"Fiscal Year",
			filters={"disabled": 0, "year_start_date": ("<=", today()), "year_end_date": (">=", today())},
		)[0]
		return frappe.get_doc("Fiscal Year", active_fy.name)

	def get_report_filters(self):
		fy = self.get_fiscal_year()
		return frappe._dict(
			company=self.company,
			from_fiscal_year=fy.name,
			to_fiscal_year=fy.name,
			period_start_date=fy.year_start_date,
			period_end_date=fy.year_end_date,
			filter_based_on="Fiscal Year",
			periodicity="Monthly",
			accumulated_vallues=True,
		)

	def test_profit_and_loss_output_and_summary(self):
		self.create_sales_invoice(qty=1, rate=150)

		filters = self.get_report_filters()
		period_list = get_period_list(
			filters.from_fiscal_year,
			filters.to_fiscal_year,
			filters.period_start_date,
			filters.period_end_date,
			filters.filter_based_on,
			filters.periodicity,
			company=filters.company,
		)

		result = execute(filters)[1]
		current_period = next(x for x in period_list if x.from_date <= getdate() and x.to_date >= getdate())
		current_period_key = current_period.key
		without_current_period = [x for x in period_list if x.key != current_period.key]
		# all period except current period(whence invoice was posted), should be '0'
		for acc in result:
			if acc:
				with self.subTest(acc=acc):
					for period in without_current_period:
						self.assertEqual(acc[period.key], 0)

		for acc in result:
			if acc:
				with self.subTest(current_period_key=current_period_key):
					self.assertEqual(acc[current_period_key], 150)
					self.assertEqual(acc["total"], 150)

	def test_p_and_l_export(self):
		self.create_sales_invoice(qty=1, rate=150)

		filters = self.get_report_filters()
		frappe.local.form_dict = frappe._dict(
			{
				"report_name": "Profit and Loss Statement",
				"file_format_type": "CSV",
				"filters": filters,
				"visible_idx": [0, 1, 2, 3, 4, 5, 6],
			}
		)
		export_query()
		contents = frappe.response["filecontent"].decode()
		sales_account = frappe.db.get_value("Company", self.company, "default_income_account")

		self.assertIn(sales_account, contents)

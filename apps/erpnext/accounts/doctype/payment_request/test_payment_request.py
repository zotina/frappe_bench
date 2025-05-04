# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import re
import unittest
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_payment_terms_template
from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request
from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.buying.doctype.purchase_order.test_purchase_order import create_purchase_order
from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order
from erpnext.setup.utils import get_exchange_rate

EXTRA_TEST_RECORD_DEPENDENCIES = ["Currency Exchange", "Journal Entry", "Contact", "Address"]

PAYMENT_URL = "https://example.com/payment"

payment_gateways = [
	{"doctype": "Payment Gateway", "gateway": "_Test Gateway"},
	{"doctype": "Payment Gateway", "gateway": "_Test Gateway Phone"},
	{"doctype": "Payment Gateway", "gateway": "_Test Gateway Other"},
]

payment_method = [
	{
		"doctype": "Payment Gateway Account",
		"is_default": 1,
		"payment_gateway": "_Test Gateway",
		"payment_account": "_Test Bank - _TC",
		"currency": "INR",
	},
	{
		"doctype": "Payment Gateway Account",
		"payment_gateway": "_Test Gateway",
		"payment_account": "_Test Bank USD - _TC",
		"currency": "USD",
	},
	{
		"doctype": "Payment Gateway Account",
		"payment_gateway": "_Test Gateway Other",
		"payment_account": "_Test Bank USD - _TC",
		"payment_channel": "Other",
		"currency": "USD",
	},
	{
		"doctype": "Payment Gateway Account",
		"payment_gateway": "_Test Gateway Phone",
		"payment_account": "_Test Bank USD - _TC",
		"payment_channel": "Phone",
		"currency": "USD",
	},
]


class UnitTestPaymentRequest(UnitTestCase):
	"""
	Unit tests for PaymentRequest.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestPaymentRequest(IntegrationTestCase):
	def setUp(self):
		for payment_gateway in payment_gateways:
			if not frappe.db.get_value("Payment Gateway", payment_gateway["gateway"], "name"):
				frappe.get_doc(payment_gateway).insert(ignore_permissions=True)

		for method in payment_method:
			if not frappe.db.get_value(
				"Payment Gateway Account",
				{"payment_gateway": method["payment_gateway"], "currency": method["currency"]},
				"name",
			):
				frappe.get_doc(method).insert(ignore_permissions=True)

		send_email = patch(
			"erpnext.accounts.doctype.payment_request.payment_request.PaymentRequest.send_email",
			return_value=None,
		)
		self.send_email = send_email.start()
		self.addCleanup(send_email.stop)
		get_payment_url = patch(
			# this also shadows one (1) call to _get_payment_gateway_controller
			"erpnext.accounts.doctype.payment_request.payment_request.PaymentRequest.get_payment_url",
			return_value=PAYMENT_URL,
		)
		self.get_payment_url = get_payment_url.start()
		self.addCleanup(get_payment_url.stop)
		_get_payment_gateway_controller = patch(
			"erpnext.accounts.doctype.payment_request.payment_request._get_payment_gateway_controller",
		)
		self._get_payment_gateway_controller = _get_payment_gateway_controller.start()
		self.addCleanup(_get_payment_gateway_controller.stop)

	def tearDown(self):
		frappe.db.rollback()

	def test_payment_request_linkings(self):
		so_inr = make_sales_order(currency="INR", do_not_save=True)
		so_inr.disable_rounded_total = 1
		so_inr.save()

		pr = make_payment_request(
			dt="Sales Order",
			dn=so_inr.name,
			recipient_id="saurabh@erpnext.com",
			payment_gateway_account="_Test Gateway - INR",
		)

		self.assertEqual(pr.reference_doctype, "Sales Order")
		self.assertEqual(pr.reference_name, so_inr.name)
		self.assertEqual(pr.currency, "INR")

		conversion_rate = get_exchange_rate("USD", "INR")

		si_usd = create_sales_invoice(currency="USD", conversion_rate=conversion_rate)
		pr = make_payment_request(
			dt="Sales Invoice",
			dn=si_usd.name,
			recipient_id="saurabh@erpnext.com",
			payment_gateway_account="_Test Gateway - USD",
		)

		self.assertEqual(pr.reference_doctype, "Sales Invoice")
		self.assertEqual(pr.reference_name, si_usd.name)
		self.assertEqual(pr.currency, "USD")

	def test_payment_channels(self):
		so = make_sales_order(currency="USD")

		pr = make_payment_request(
			dt="Sales Order",
			dn=so.name,
			payment_gateway_account="_Test Gateway Other - USD",
			submit_doc=True,
			return_doc=True,
		)
		self.assertEqual(pr.payment_channel, "Other")
		self.assertEqual(pr.mute_email, True)

		self.assertEqual(pr.payment_url, PAYMENT_URL)
		self.assertEqual(self.send_email.call_count, 0)
		self.assertEqual(self._get_payment_gateway_controller.call_count, 1)
		pr.cancel()

		pr = make_payment_request(
			dt="Sales Order",
			dn=so.name,
			payment_gateway_account="_Test Gateway - USD",  # email channel
			submit_doc=False,
			return_doc=True,
		)
		pr.flags.mute_email = True  # but temporarily prohibit sending
		pr.submit()
		pr.reload()
		self.assertEqual(pr.payment_channel, "Email")
		self.assertEqual(pr.mute_email, False)

		self.assertEqual(pr.payment_url, PAYMENT_URL)
		self.assertEqual(self.send_email.call_count, 0)  # hence: no increment
		self.assertEqual(self._get_payment_gateway_controller.call_count, 2)
		pr.cancel()

		pr = make_payment_request(
			dt="Sales Order",
			dn=so.name,
			payment_gateway_account="_Test Gateway Phone - USD",
			submit_doc=True,
			return_doc=True,
		)
		pr.reload()

		self.assertEqual(pr.payment_channel, "Phone")
		self.assertEqual(pr.mute_email, True)

		self.assertIsNone(pr.payment_url)
		self.assertEqual(self.send_email.call_count, 0)  # no increment on phone channel
		self.assertEqual(self._get_payment_gateway_controller.call_count, 3)
		pr.cancel()

		pr = make_payment_request(
			dt="Sales Order",
			dn=so.name,
			payment_gateway_account="_Test Gateway - USD",  # email channel
			submit_doc=True,
			return_doc=True,
		)
		pr.reload()

		self.assertEqual(pr.payment_channel, "Email")
		self.assertEqual(pr.mute_email, False)

		self.assertEqual(pr.payment_url, PAYMENT_URL)
		self.assertEqual(self.send_email.call_count, 1)  # increment on normal email channel
		self.assertEqual(self._get_payment_gateway_controller.call_count, 4)
		pr.cancel()

		so = make_sales_order(currency="USD", do_not_save=True)
		# no-op; for optical consistency with how a webshop SO would look like
		so.order_type = "Shopping Cart"
		so.save()
		pr = make_payment_request(
			dt="Sales Order",
			dn=so.name,
			payment_gateway_account="_Test Gateway - USD",  # email channel
			make_sales_invoice=True,
			mute_email=True,
			submit_doc=True,
			return_doc=True,
		)
		pr.reload()

		self.assertEqual(pr.payment_channel, "Email")
		self.assertEqual(pr.mute_email, True)

		self.assertEqual(pr.payment_url, PAYMENT_URL)
		self.assertEqual(self.send_email.call_count, 1)  # no increment on shopping cart
		self.assertEqual(self._get_payment_gateway_controller.call_count, 5)
		pr.cancel()

	def test_payment_entry_against_purchase_invoice(self):
		si_usd = make_purchase_invoice(
			supplier="_Test Supplier USD",
			debit_to="_Test Payable USD - _TC",
			currency="USD",
			conversion_rate=50,
		)

		pr = make_payment_request(
			dt="Purchase Invoice",
			dn=si_usd.name,
			party_type="Supplier",
			party="_Test Supplier USD",
			recipient_id="user@example.com",
			mute_email=1,
			payment_gateway_account="_Test Gateway - USD",
			submit_doc=1,
			return_doc=1,
		)

		pr.create_payment_entry()
		pr.load_from_db()

		self.assertEqual(pr.status, "Paid")

	def test_multiple_payment_entry_against_purchase_invoice(self):
		purchase_invoice = make_purchase_invoice(
			supplier="_Test Supplier USD",
			debit_to="_Test Payable USD - _TC",
			currency="USD",
			conversion_rate=50,
		)

		pr = make_payment_request(
			dt="Purchase Invoice",
			party_type="Supplier",
			party="_Test Supplier USD",
			dn=purchase_invoice.name,
			recipient_id="user@example.com",
			mute_email=1,
			payment_gateway_account="_Test Gateway - USD",
			return_doc=1,
		)

		pr.grand_total = pr.grand_total / 2

		pr.submit()
		pr.create_payment_entry()

		purchase_invoice.load_from_db()
		self.assertEqual(purchase_invoice.status, "Partly Paid")

		pr = make_payment_request(
			dt="Purchase Invoice",
			party_type="Supplier",
			party="_Test Supplier USD",
			dn=purchase_invoice.name,
			recipient_id="user@example.com",
			mute_email=1,
			payment_gateway_account="_Test Gateway - USD",
			return_doc=1,
		)

		pr.save()
		pr.submit()
		pr.create_payment_entry()

		purchase_invoice.load_from_db()
		self.assertEqual(purchase_invoice.status, "Paid")

	def test_payment_entry(self):
		frappe.db.set_value(
			"Company", "_Test Company", "exchange_gain_loss_account", "_Test Exchange Gain/Loss - _TC"
		)
		frappe.db.set_value("Company", "_Test Company", "write_off_account", "_Test Write Off - _TC")
		frappe.db.set_value("Company", "_Test Company", "cost_center", "_Test Cost Center - _TC")

		so_inr = make_sales_order(currency="INR")
		pr = make_payment_request(
			dt="Sales Order",
			dn=so_inr.name,
			recipient_id="saurabh@erpnext.com",
			mute_email=1,
			payment_gateway_account="_Test Gateway - INR",
			submit_doc=1,
			return_doc=1,
		)
		pe = pr.set_as_paid()

		so_inr = frappe.get_doc("Sales Order", so_inr.name)

		self.assertEqual(so_inr.advance_paid, 1000)

		si_usd = create_sales_invoice(
			customer="_Test Customer USD",
			debit_to="_Test Receivable USD - _TC",
			currency="USD",
			conversion_rate=50,
		)

		pr = make_payment_request(
			dt="Sales Invoice",
			dn=si_usd.name,
			recipient_id="saurabh@erpnext.com",
			mute_email=1,
			payment_gateway_account="_Test Gateway - USD",
			submit_doc=1,
			return_doc=1,
		)

		pe = pr.set_as_paid()

		expected_gle = dict(
			(d[0], d)
			for d in [
				["_Test Receivable USD - _TC", 0, 5000, si_usd.name],
				[pr.payment_account, 5000.0, 0, None],
			]
		)

		gl_entries = frappe.db.sql(
			"""select account, debit, credit, against_voucher
			from `tabGL Entry` where voucher_type='Payment Entry' and voucher_no=%s
			order by account asc""",
			pe.name,
			as_dict=1,
		)

		self.assertTrue(gl_entries)

		for _i, gle in enumerate(gl_entries):
			self.assertEqual(expected_gle[gle.account][0], gle.account)
			self.assertEqual(expected_gle[gle.account][1], gle.debit)
			self.assertEqual(expected_gle[gle.account][2], gle.credit)
			self.assertEqual(expected_gle[gle.account][3], gle.against_voucher)

	def test_status(self):
		si_usd = create_sales_invoice(
			customer="_Test Customer USD",
			debit_to="_Test Receivable USD - _TC",
			currency="USD",
			conversion_rate=50,
		)

		pr = make_payment_request(
			dt="Sales Invoice",
			dn=si_usd.name,
			recipient_id="saurabh@erpnext.com",
			mute_email=1,
			payment_gateway_account="_Test Gateway - USD",
			submit_doc=1,
			return_doc=1,
		)

		pe = pr.create_payment_entry()
		pr.load_from_db()

		self.assertEqual(pr.status, "Paid")

		pe.cancel()
		pr.load_from_db()

		self.assertEqual(pr.status, "Requested")

	def test_multiple_payment_entries_against_sales_order(self):
		# Make Sales Order, grand_total = 1000
		so = make_sales_order()

		# Payment Request amount = 200
		pr1 = make_payment_request(
			dt="Sales Order", dn=so.name, recipient_id="nabin@erpnext.com", return_doc=1
		)
		pr1.grand_total = 200
		pr1.submit()

		# Make a 2nd Payment Request
		pr2 = make_payment_request(
			dt="Sales Order", dn=so.name, recipient_id="nabin@erpnext.com", return_doc=1
		)

		self.assertEqual(pr2.grand_total, 800)

		# Try to make Payment Request more than SO amount, should give validation
		pr2.grand_total = 900
		self.assertRaises(frappe.ValidationError, pr2.save)

	def test_conversion_on_foreign_currency_accounts(self):
		po_doc = create_purchase_order(supplier="_Test Supplier USD", currency="USD", do_not_submit=1)
		po_doc.conversion_rate = 80
		po_doc.items[0].qty = 1
		po_doc.items[0].rate = 10
		po_doc.save().submit()

		pr = make_payment_request(dt=po_doc.doctype, dn=po_doc.name, recipient_id="nabin@erpnext.com")
		pr = frappe.get_doc(pr).save().submit()

		pe = pr.create_payment_entry()
		self.assertEqual(pe.base_paid_amount, 800)
		self.assertEqual(pe.paid_amount, 800)
		self.assertEqual(pe.base_received_amount, 800)
		self.assertEqual(pe.received_amount, 10)

	def test_multiple_payment_if_partially_paid_for_same_currency(self):
		so = make_sales_order(currency="INR", qty=1, rate=1000)

		self.assertEqual(so.advance_payment_status, "Not Requested")

		pr = make_payment_request(
			dt="Sales Order",
			dn=so.name,
			mute_email=1,
			submit_doc=1,
			return_doc=1,
		)

		self.assertEqual(pr.grand_total, 1000)
		self.assertEqual(pr.outstanding_amount, pr.grand_total)
		self.assertEqual(pr.party_account_currency, pr.currency)  # INR
		self.assertEqual(pr.status, "Requested")

		so.load_from_db()
		self.assertEqual(so.advance_payment_status, "Requested")

		# to make partial payment
		pe = pr.create_payment_entry(submit=False)
		pe.paid_amount = 200
		pe.references[0].allocated_amount = 200
		pe.submit()

		self.assertEqual(pe.references[0].payment_request, pr.name)

		so.load_from_db()
		self.assertEqual(so.advance_payment_status, "Partially Paid")

		pr.load_from_db()
		self.assertEqual(pr.status, "Partially Paid")
		self.assertEqual(pr.outstanding_amount, 800)
		self.assertEqual(pr.grand_total, 1000)

		self.assertRaisesRegex(
			frappe.exceptions.ValidationError,
			re.compile(r"Payment Request is already created"),
			make_payment_request,
			dt="Sales Order",
			dn=so.name,
			mute_email=1,
			submit_doc=1,
			return_doc=1,
		)
		# complete payment
		pe = pr.create_payment_entry()

		self.assertEqual(pe.paid_amount, 800)  # paid amount set from pr's outstanding amount
		self.assertEqual(pe.references[0].allocated_amount, 800)
		self.assertEqual(pe.references[0].outstanding_amount, 800)  # for Orders it is not zero
		self.assertEqual(pe.references[0].payment_request, pr.name)

		so.load_from_db()
		self.assertEqual(so.advance_payment_status, "Fully Paid")

		pr.load_from_db()
		self.assertEqual(pr.status, "Paid")
		self.assertEqual(pr.outstanding_amount, 0)
		self.assertEqual(pr.grand_total, 1000)

		# creating a more payment Request must not allowed
		self.assertRaisesRegex(
			frappe.exceptions.ValidationError,
			re.compile(r"Payment Entry is already created"),
			make_payment_request,
			dt="Sales Order",
			dn=so.name,
			mute_email=1,
			submit_doc=1,
			return_doc=1,
		)

	@IntegrationTestCase.change_settings(
		"Accounts Settings", {"allow_multi_currency_invoices_against_single_party_account": 1}
	)
	def test_multiple_payment_if_partially_paid_for_multi_currency(self):
		pi = make_purchase_invoice(currency="USD", conversion_rate=50, qty=1, rate=100, do_not_save=1)
		pi.credit_to = "Creditors - _TC"
		pi.submit()

		pr = make_payment_request(
			dt="Purchase Invoice",
			dn=pi.name,
			mute_email=1,
			submit_doc=1,
			return_doc=1,
		)

		# 100 USD -> 5000 INR
		self.assertEqual(pr.grand_total, 100)
		self.assertEqual(pr.outstanding_amount, 5000)
		self.assertEqual(pr.currency, "USD")
		self.assertEqual(pr.party_account_currency, "INR")
		self.assertEqual(pr.status, "Initiated")

		self.assertRaisesRegex(
			frappe.exceptions.ValidationError,
			re.compile(r"Payment Request is already created"),
			make_payment_request,
			dt="Purchase Invoice",
			dn=pi.name,
			mute_email=1,
			submit_doc=1,
			return_doc=1,
		)

		# to make partial payment
		pe = pr.create_payment_entry(submit=False)
		pe.paid_amount = 2000
		pe.references[0].allocated_amount = 2000
		pe.submit()

		self.assertEqual(pe.references[0].payment_request, pr.name)

		pr.load_from_db()
		self.assertEqual(pr.status, "Partially Paid")
		self.assertEqual(pr.outstanding_amount, 3000)
		self.assertEqual(pr.grand_total, 100)

		# complete payment
		pe = pr.create_payment_entry()
		self.assertEqual(pe.paid_amount, 3000)  # paid amount set from pr's outstanding amount
		self.assertEqual(pe.references[0].allocated_amount, 3000)
		self.assertEqual(pe.references[0].outstanding_amount, 0)  # for Invoices it will zero
		self.assertEqual(pe.references[0].payment_request, pr.name)

		pr.load_from_db()
		self.assertEqual(pr.status, "Paid")
		self.assertEqual(pr.outstanding_amount, 0)
		self.assertEqual(pr.grand_total, 100)

		# creating a more payment Request must not allowed
		self.assertRaisesRegex(
			frappe.exceptions.ValidationError,
			re.compile(r"Payment Entry is already created"),
			make_payment_request,
			dt="Purchase Invoice",
			dn=pi.name,
			mute_email=1,
			submit_doc=1,
			return_doc=1,
		)

	def test_single_payment_with_payment_term_for_same_currency(self):
		create_payment_terms_template()

		po = create_purchase_order(do_not_save=1, currency="INR", qty=1, rate=20000)
		po.payment_terms_template = "Test Receivable Template"  # 84.746 and 15.254
		po.save()
		po.submit()

		self.assertEqual(po.advance_payment_status, "Not Initiated")

		pr = make_payment_request(
			dt="Purchase Order",
			dn=po.name,
			mute_email=1,
			submit_doc=1,
			return_doc=1,
		)

		self.assertEqual(pr.grand_total, 20000)
		self.assertEqual(pr.outstanding_amount, pr.grand_total)
		self.assertEqual(pr.party_account_currency, pr.currency)  # INR
		self.assertEqual(pr.status, "Initiated")

		po.load_from_db()
		self.assertEqual(po.advance_payment_status, "Initiated")

		pe = pr.create_payment_entry()

		self.assertEqual(len(pe.references), 2)
		self.assertEqual(pe.paid_amount, 20000)

		# check 1st payment term
		self.assertEqual(pe.references[0].allocated_amount, 16949.2)
		self.assertEqual(pe.references[0].payment_request, pr.name)

		# check 2nd payment term
		self.assertEqual(pe.references[1].allocated_amount, 3050.8)
		self.assertEqual(pe.references[1].payment_request, pr.name)

		po.load_from_db()
		self.assertEqual(po.advance_payment_status, "Fully Paid")

		pr.load_from_db()
		self.assertEqual(pr.status, "Paid")
		self.assertEqual(pr.outstanding_amount, 0)
		self.assertEqual(pr.grand_total, 20000)

	@IntegrationTestCase.change_settings(
		"Accounts Settings", {"allow_multi_currency_invoices_against_single_party_account": 1}
	)
	def test_single_payment_with_payment_term_for_multi_currency(self):
		create_payment_terms_template()

		si = create_sales_invoice(
			do_not_save=1, currency="USD", debit_to="Debtors - _TC", qty=1, rate=200, conversion_rate=50
		)
		si.payment_terms_template = "Test Receivable Template"  # 84.746 and 15.254
		si.save()
		si.submit()

		pr = make_payment_request(
			dt="Sales Invoice",
			dn=si.name,
			mute_email=1,
			submit_doc=1,
			return_doc=1,
		)

		# 200 USD -> 10000 INR
		self.assertEqual(pr.grand_total, 200)
		self.assertEqual(pr.outstanding_amount, 10000)
		self.assertEqual(pr.currency, "USD")
		self.assertEqual(pr.party_account_currency, "INR")
		self.assertEqual(pr.status, "Requested")

		pe = pr.create_payment_entry()
		self.assertEqual(len(pe.references), 2)
		self.assertEqual(pe.paid_amount, 10000)

		# check 1st payment term
		# convert it via dollar and conversion_rate
		self.assertEqual(pe.references[0].allocated_amount, 8474.5)  # multi currency conversion
		self.assertEqual(pe.references[0].payment_request, pr.name)

		# check 2nd payment term
		self.assertEqual(pe.references[1].allocated_amount, 1525.5)  # multi currency conversion
		self.assertEqual(pe.references[1].payment_request, pr.name)

		pr.load_from_db()
		self.assertEqual(pr.status, "Paid")
		self.assertEqual(pr.outstanding_amount, 0)
		self.assertEqual(pr.grand_total, 200)

	def test_payment_cancel_process(self):
		so = make_sales_order(currency="INR", qty=1, rate=1000)
		self.assertEqual(so.advance_payment_status, "Not Requested")

		pr = make_payment_request(
			dt="Sales Order",
			dn=so.name,
			mute_email=1,
			submit_doc=1,
			return_doc=1,
		)

		self.assertEqual(pr.status, "Requested")
		self.assertEqual(pr.grand_total, 1000)
		self.assertEqual(pr.outstanding_amount, pr.grand_total)

		so.load_from_db()
		self.assertEqual(so.advance_payment_status, "Requested")

		pe = pr.create_payment_entry(submit=False)
		pe.paid_amount = 800
		pe.references[0].allocated_amount = 800
		pe.submit()

		self.assertEqual(pe.references[0].payment_request, pr.name)

		so.load_from_db()
		self.assertEqual(so.advance_payment_status, "Partially Paid")

		pr.load_from_db()
		self.assertEqual(pr.status, "Partially Paid")
		self.assertEqual(pr.outstanding_amount, 200)
		self.assertEqual(pr.grand_total, 1000)

		# cancelling PE
		pe.cancel()

		pr.load_from_db()
		self.assertEqual(pr.status, "Requested")
		self.assertEqual(pr.outstanding_amount, 1000)
		self.assertEqual(pr.grand_total, 1000)

		so.load_from_db()
		self.assertEqual(so.advance_payment_status, "Requested")

	def test_partial_paid_invoice_with_payment_request(self):
		si = create_sales_invoice(currency="INR", qty=1, rate=5000)
		si.save()
		si.submit()

		pe = get_payment_entry("Sales Invoice", si.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "PAYEE0002"
		pe.reference_date = frappe.utils.nowdate()
		pe.paid_amount = 2500
		pe.references[0].allocated_amount = 2500
		pe.save()
		pe.submit()

		si.load_from_db()
		pr = make_payment_request(dt="Sales Invoice", dn=si.name, mute_email=1)

		self.assertEqual(pr.grand_total, si.outstanding_amount)

	def test_partial_paid_invoice_with_more_payment_entry(self):
		pi = make_purchase_invoice(currency="INR", qty=1, rate=500)
		pi.submit()
		pi_1 = make_purchase_invoice(currency="INR", qty=1, rate=300)
		pi_1.submit()

		pr = make_payment_request(dt="Purchase Invoice", dn=pi.name, mute_email=1, submit_doc=0, return_doc=1)
		pr.grand_total = 200
		pr.submit()
		pr.create_payment_entry()
		pr_1 = make_payment_request(
			dt="Purchase Invoice", dn=pi.name, mute_email=1, submit_doc=0, return_doc=1
		)
		pr_1.grand_total = 200
		pr_1.submit()
		pr_1.create_payment_entry()

		pe = get_payment_entry(dt="Purchase Invoice", dn=pi.name)
		pe.paid_amount = 200
		pe.references[0].reference_doctype = pi.doctype
		pe.references[0].reference_name = pi.name
		pe.references[0].grand_total = pi.grand_total
		pe.references[0].outstanding_amount = pi.outstanding_amount
		pe.references[0].allocated_amount = 100
		pe.append(
			"references",
			{
				"reference_doctype": pi_1.doctype,
				"reference_name": pi_1.name,
				"grand_total": pi_1.grand_total,
				"outstanding_amount": pi_1.outstanding_amount,
				"allocated_amount": 100,
			},
		)

		pr_2 = make_payment_request(dt="Purchase Invoice", dn=pi.name, mute_email=1)
		pi.load_from_db()
		self.assertEqual(pr_2.grand_total, pi.outstanding_amount)

	def test_consider_journal_entry_and_return_invoice(self):
		from erpnext.accounts.doctype.journal_entry.test_journal_entry import make_journal_entry

		si = create_sales_invoice(currency="INR", qty=5, rate=500)

		je = make_journal_entry("_Test Cash - _TC", "Debtors - _TC", 500, save=False)
		je.accounts[1].party_type = "Customer"
		je.accounts[1].party = si.customer
		je.accounts[1].reference_type = "Sales Invoice"
		je.accounts[1].reference_name = si.name
		je.accounts[1].credit_in_account_currency = 500
		je.submit()

		pe = get_payment_entry("Sales Invoice", si.name)
		pe.paid_amount = 500
		pe.references[0].allocated_amount = 500
		pe.save()
		pe.submit()

		cr_note = create_sales_invoice(qty=-1, rate=500, is_return=1, return_against=si.name, do_not_save=1)
		cr_note.update_outstanding_for_self = 0
		cr_note.save()
		cr_note.submit()

		si.load_from_db()
		pr = make_payment_request(dt="Sales Invoice", dn=si.name, mute_email=1)
		self.assertEqual(pr.grand_total, si.outstanding_amount)


def test_partial_paid_invoice_with_submitted_payment_entry(self):
	pi = make_purchase_invoice(currency="INR", qty=1, rate=5000)
	pi.save()
	pi.submit()

	pe = get_payment_entry("Purchase Invoice", pi.name, bank_account="_Test Bank - _TC")
	pe.reference_no = "PURINV0001"
	pe.reference_date = frappe.utils.nowdate()
	pe.paid_amount = 2500
	pe.references[0].allocated_amount = 2500
	pe.save()
	pe.submit()
	pe.cancel()

	pe = get_payment_entry("Purchase Invoice", pi.name, bank_account="_Test Bank - _TC")
	pe.reference_no = "PURINV0002"
	pe.reference_date = frappe.utils.nowdate()
	pe.paid_amount = 2500
	pe.references[0].allocated_amount = 2500
	pe.save()
	pe.submit()

	pi.load_from_db()
	pr = make_payment_request(dt="Purchase Invoice", dn=pi.name, mute_email=1)
	self.assertEqual(pr.grand_total, pi.outstanding_amount)

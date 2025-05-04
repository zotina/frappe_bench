# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import map_child_doc, map_doc
from frappe.query_builder import DocType
from frappe.utils import cint, flt, get_time, getdate, nowdate, nowtime
from frappe.utils.background_jobs import enqueue, is_job_enqueued
from frappe.utils.scheduler import is_scheduler_inactive

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_checks_for_pl_and_bs_accounts,
)
from erpnext.controllers.taxes_and_totals import ItemWiseTaxDetail


class POSInvoiceMergeLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.accounts.doctype.pos_invoice_reference.pos_invoice_reference import (
			POSInvoiceReference,
		)

		amended_from: DF.Link | None
		consolidated_credit_note: DF.Link | None
		consolidated_invoice: DF.Link | None
		customer: DF.Link
		customer_group: DF.Link | None
		merge_invoices_based_on: DF.Literal["Customer", "Customer Group"]
		pos_closing_entry: DF.Link | None
		pos_invoices: DF.Table[POSInvoiceReference]
		posting_date: DF.Date
		posting_time: DF.Time
	# end: auto-generated types

	def validate(self):
		self.validate_customer()
		self.validate_pos_invoice_status()
		self.validate_duplicate_pos_invoices()

	def validate_duplicate_pos_invoices(self):
		pos_occurences = {}
		for idx, inv in enumerate(self.pos_invoices, 1):
			pos_occurences.setdefault(inv.pos_invoice, []).append(idx)

		error_list = []
		for key, value in pos_occurences.items():
			if len(value) > 1:
				error_list.append(
					_("{0} is added multiple times on rows: {1}").format(frappe.bold(key), frappe.bold(value))
				)

		if error_list:
			frappe.throw(error_list, title=_("Duplicate POS Invoices found"), as_list=True)

	def validate_customer(self):
		if self.merge_invoices_based_on == "Customer Group":
			return

		for d in self.pos_invoices:
			if d.customer != self.customer:
				frappe.throw(
					_("Row #{}: POS Invoice {} is not against customer {}").format(
						d.idx, d.pos_invoice, self.customer
					)
				)

	def validate_pos_invoice_status(self):
		for d in self.pos_invoices:
			status, docstatus, is_return, return_against = frappe.db.get_value(
				"POS Invoice", d.pos_invoice, ["status", "docstatus", "is_return", "return_against"]
			)

			bold_pos_invoice = frappe.bold(d.pos_invoice)
			bold_status = frappe.bold(status)
			if docstatus != 1:
				frappe.throw(
					_("Row #{}: POS Invoice {} is not submitted yet").format(d.idx, bold_pos_invoice)
				)
			if status == "Consolidated":
				frappe.throw(
					_("Row #{}: POS Invoice {} has been {}").format(d.idx, bold_pos_invoice, bold_status)
				)
			if (
				is_return
				and return_against
				and return_against not in [d.pos_invoice for d in self.pos_invoices]
			):
				bold_return_against = frappe.bold(return_against)
				return_against_status = frappe.db.get_value("POS Invoice", return_against, "status")
				if return_against_status != "Consolidated":
					# if return entry is not getting merged in the current pos closing and if it is not consolidated
					msg = _(
						"Row #{}: The original Invoice {} of return invoice {} is not consolidated."
					).format(d.idx, bold_return_against, bold_pos_invoice)
					msg += " "
					msg += _(
						"The original invoice should be consolidated before or along with the return invoice."
					)
					msg += "<br><br>"
					msg += _("You can add the original invoice {} manually to proceed.").format(
						bold_return_against
					)
					frappe.throw(msg)

	def on_submit(self):
		pos_invoice_docs = [frappe.get_cached_doc("POS Invoice", d.pos_invoice) for d in self.pos_invoices]

		returns = [d for d in pos_invoice_docs if d.get("is_return") == 1]
		sales = [d for d in pos_invoice_docs if d.get("is_return") == 0]

		sales_invoice, credit_notes = "", {}
		sales_invoice_doc = None
		if sales:
			sales_invoice_doc = self.process_merging_into_sales_invoice(sales)
			sales_invoice = sales_invoice_doc.name

		if returns:
			distinguished_returns = self.distinguish_return_pos_invoices(returns, sales_invoice_doc)
			credit_notes = self.process_merging_into_credit_notes(distinguished_returns)

		self.save()  # save consolidated_sales_invoice & consolidated_credit_note ref in merge log
		self.update_pos_invoices(pos_invoice_docs, sales_invoice, credit_notes)

	def on_cancel(self):
		pos_invoice_docs = [frappe.get_cached_doc("POS Invoice", d.pos_invoice) for d in self.pos_invoices]

		self.update_pos_invoices(pos_invoice_docs)
		self.serial_and_batch_bundle_reference_for_pos_invoice()
		self.cancel_linked_invoices()
		self.delink_serial_and_batch_bundle()

	def process_merging_into_sales_invoice(self, data):
		sales_invoice = self.get_new_sales_invoice()
		sales_invoice = self.merge_pos_invoice_into(sales_invoice, data)

		sales_invoice.is_consolidated = 1
		sales_invoice.set_posting_time = 1

		if not sales_invoice.posting_date:
			sales_invoice.posting_date = getdate(self.posting_date)

		if not sales_invoice.posting_time:
			sales_invoice.posting_time = get_time(self.posting_time)

		sales_invoice.save()
		sales_invoice.submit()

		self.consolidated_invoice = sales_invoice.name

		return sales_invoice

	def process_merging_into_credit_notes(self, data):
		credit_notes = {}
		for key, value in data.items():
			if not value:
				continue

			credit_note = self.get_new_sales_invoice()
			credit_note.is_return = 1

			credit_note = self.merge_pos_invoice_into(credit_note, value)
			credit_note.return_against = key

			credit_note.is_consolidated = 1
			credit_note.set_posting_time = 1
			credit_note.posting_date = getdate(self.posting_date)
			credit_note.posting_time = get_time(self.posting_time)
			# TODO: return could be against multiple sales invoice which could also have been consolidated?
			# credit_note.return_against = self.consolidated_invoice
			credit_note.save()
			credit_note.submit()

			self.consolidated_credit_note = credit_note.name
			credit_notes[credit_note.name] = [d.name for d in value]

		return credit_notes

	def distinguish_return_pos_invoices(self, data, sales_invoice_doc=None):
		return_invoices = {}

		return_invoices[sales_invoice_doc.name if sales_invoice_doc else None] = []

		for doc in data:
			sales_invoices_of_return_against = frappe.db.get_value(
				"POS Invoice", doc.return_against, "consolidated_invoice"
			)
			if sales_invoices_of_return_against:
				if sales_invoices_of_return_against in return_invoices:
					return_invoices[sales_invoices_of_return_against].append(doc)
				else:
					return_invoices[sales_invoices_of_return_against] = [doc]
			else:
				return_invoices[sales_invoice_doc.name if sales_invoice_doc else None].append(doc)

		return return_invoices

	def merge_pos_invoice_into(self, invoice, data):
		items, payments, taxes = [], [], []

		loyalty_amount_sum, loyalty_points_sum = 0, 0

		rounding_adjustment, base_rounding_adjustment = 0, 0
		rounded_total, base_rounded_total = 0, 0

		loyalty_amount_sum, loyalty_points_sum, idx = 0, 0, 1

		for doc in data:
			map_doc(doc, invoice, table_map={"doctype": invoice.doctype})

			if doc.get("posting_date"):
				invoice.posting_date = getdate(doc.posting_date)
				invoice.posting_time = get_time(doc.posting_time)

			if doc.redeem_loyalty_points:
				invoice.loyalty_redemption_account = doc.loyalty_redemption_account
				invoice.loyalty_redemption_cost_center = doc.loyalty_redemption_cost_center
				loyalty_points_sum += doc.loyalty_points
				loyalty_amount_sum += doc.loyalty_amount

			for item in doc.get("items"):
				item.rate = item.net_rate
				item.amount = item.net_amount
				item.base_amount = item.base_net_amount
				item.price_list_rate = 0
				si_item = map_child_doc(item, invoice, {"doctype": "Sales Invoice Item"})
				si_item.pos_invoice = doc.name
				si_item.pos_invoice_item = item.name
				if doc.is_return:
					si_item.sales_invoice_item = get_sales_invoice_item(
						doc.return_against, item.pos_invoice_item
					)
				if item.serial_and_batch_bundle:
					si_item.serial_and_batch_bundle = item.serial_and_batch_bundle
				items.append(si_item)

			for tax in doc.get("taxes"):
				found = False
				for t in taxes:
					if t.account_head == tax.account_head and t.cost_center == tax.cost_center:
						t.tax_amount = flt(t.tax_amount) + flt(tax.tax_amount_after_discount_amount)
						t.base_tax_amount = flt(t.base_tax_amount) + flt(
							tax.base_tax_amount_after_discount_amount
						)
						update_item_wise_tax_detail(t, tax)
						found = True
				if not found:
					tax.charge_type = "Actual"
					tax.idx = idx
					idx += 1
					tax.included_in_print_rate = 0
					tax.tax_amount = tax.tax_amount_after_discount_amount
					tax.base_tax_amount = tax.base_tax_amount_after_discount_amount
					tax.item_wise_tax_detail = tax.item_wise_tax_detail
					taxes.append(tax)

			for payment in doc.get("payments"):
				found = False
				for pay in payments:
					if pay.account == payment.account and pay.mode_of_payment == payment.mode_of_payment:
						pay.amount = flt(pay.amount) + flt(payment.amount)
						pay.base_amount = flt(pay.base_amount) + flt(payment.base_amount)
						found = True
				if not found:
					payments.append(payment)

			rounding_adjustment += doc.rounding_adjustment
			rounded_total += doc.rounded_total
			base_rounding_adjustment += doc.base_rounding_adjustment
			base_rounded_total += doc.base_rounded_total

		if loyalty_points_sum:
			invoice.redeem_loyalty_points = 1
			invoice.loyalty_points = loyalty_points_sum
			invoice.loyalty_amount = loyalty_amount_sum

		invoice.set("items", items)
		invoice.set("payments", payments)
		invoice.set("taxes", taxes)
		invoice.set("rounding_adjustment", rounding_adjustment)
		invoice.set("base_rounding_adjustment", base_rounding_adjustment)
		invoice.set("rounded_total", rounded_total)
		invoice.set("base_rounded_total", base_rounded_total)
		invoice.additional_discount_percentage = 0
		invoice.discount_amount = 0.0
		invoice.taxes_and_charges = None
		invoice.ignore_pricing_rule = 1
		invoice.customer = self.customer
		invoice.disable_rounded_total = cint(
			frappe.db.get_value("POS Profile", invoice.pos_profile, "disable_rounded_total")
		)
		accounting_dimensions = get_checks_for_pl_and_bs_accounts()
		accounting_dimensions_fields = [d.fieldname for d in accounting_dimensions]
		dimension_values = frappe.db.get_value(
			"POS Profile", {"name": invoice.pos_profile}, accounting_dimensions_fields, as_dict=1
		)
		for dimension in accounting_dimensions:
			dimension_value = dimension_values.get(dimension.fieldname)

			if not dimension_value and (dimension.mandatory_for_pl or dimension.mandatory_for_bs):
				frappe.throw(
					_("Please set Accounting Dimension {} in {}").format(
						frappe.bold(dimension.label),
						frappe.get_desk_link("POS Profile", invoice.pos_profile),
					)
				)

			invoice.set(dimension.fieldname, dimension_value)

		if self.merge_invoices_based_on == "Customer Group":
			invoice.flags.ignore_pos_profile = True
			invoice.pos_profile = ""

		return invoice

	def get_new_sales_invoice(self):
		sales_invoice = frappe.new_doc("Sales Invoice")
		sales_invoice.customer = self.customer
		sales_invoice.is_pos = 1
		sales_invoice.posting_date = None
		sales_invoice.posting_time = None

		return sales_invoice

	def update_pos_invoices(self, invoice_docs, sales_invoice="", credit_notes=None):
		for doc in invoice_docs:
			doc.load_from_db()
			inv = sales_invoice
			if doc.is_return:
				for key, value in credit_notes.items():
					if doc.name in value:
						inv = key
						break
			doc.update({"consolidated_invoice": None if self.docstatus == 2 else inv})
			doc.set_status(update=True)
			doc.save()

	def serial_and_batch_bundle_reference_for_pos_invoice(self):
		for d in self.pos_invoices:
			pos_invoice = frappe.get_doc("POS Invoice", d.pos_invoice)
			for table_name in ["items", "packed_items"]:
				pos_invoice.set_serial_and_batch_bundle(table_name)

	def delink_serial_and_batch_bundle(self):
		bundles = self.get_serial_and_batch_bundles()
		if not bundles:
			return

		sle_table = frappe.qb.DocType("Stock Ledger Entry")
		query = (
			frappe.qb.update(sle_table)
			.set(sle_table.serial_and_batch_bundle, None)
			.where(sle_table.serial_and_batch_bundle.isin(bundles) & sle_table.is_cancelled == 1)
		)

		query.run()

	def get_serial_and_batch_bundles(self):
		pos_invoices = []
		for d in self.pos_invoices:
			pos_invoices.append(d.pos_invoice)

		if pos_invoices:
			return frappe.get_all(
				"POS Invoice Item",
				filters={
					"docstatus": 1,
					"parent": ["in", pos_invoices],
					"serial_and_batch_bundle": ["is", "set"],
				},
				pluck="serial_and_batch_bundle",
			)

		return []

	def cancel_linked_invoices(self):
		invoices = [self.consolidated_invoice, self.consolidated_credit_note]
		if not invoices:
			return

		invoices.reverse()
		for si_name in invoices:
			if not si_name:
				continue
			si = frappe.get_doc("Sales Invoice", si_name)
			si.flags.ignore_validate = True
			si.cancel()


def update_item_wise_tax_detail(consolidate_tax_row, tax_row):
	consolidated_tax_detail = json.loads(consolidate_tax_row.item_wise_tax_detail)
	tax_row_detail = json.loads(tax_row.item_wise_tax_detail)

	if not consolidated_tax_detail:
		consolidated_tax_detail = {}

	for item_code, tax_data in tax_row_detail.items():
		tax_data = ItemWiseTaxDetail(**tax_data)
		if consolidated_tax_detail.get(item_code):
			consolidated_tax_detail[item_code]["tax_amount"] += tax_data.tax_amount
			consolidated_tax_detail[item_code]["net_amount"] += tax_data.net_amount
		else:
			consolidated_tax_detail.update({item_code: tax_data})

	consolidate_tax_row.item_wise_tax_detail = json.dumps(consolidated_tax_detail)


def get_all_unconsolidated_invoices():
	filters = {
		"consolidated_invoice": ["in", ["", None]],
		"status": ["not in", ["Consolidated"]],
		"docstatus": 1,
	}
	pos_invoices = frappe.db.get_all(
		"POS Invoice",
		filters=filters,
		fields=[
			"name as pos_invoice",
			"posting_date",
			"grand_total",
			"customer",
			"is_return",
			"return_against",
		],
	)

	return pos_invoices


def get_invoice_customer_map(pos_invoices):
	# pos_invoice_customer_map = { 'Customer 1': [{}, {}, {}], 'Customer 2' : [{}] }
	pos_invoice_customer_map = {}
	for invoice in pos_invoices:
		customer = invoice.get("customer")
		pos_invoice_customer_map.setdefault(customer, [])
		pos_invoice_customer_map[customer].append(invoice)

	return pos_invoice_customer_map


def consolidate_pos_invoices(pos_invoices=None, closing_entry=None):
	invoices = pos_invoices or (closing_entry and closing_entry.get("pos_transactions"))
	if frappe.flags.in_test and not invoices:
		invoices = get_all_unconsolidated_invoices()

	invoice_by_customer = get_invoice_customer_map(invoices)

	if len(invoices) >= 10 and closing_entry:
		closing_entry.set_status(update=True, status="Queued")
		enqueue_job(create_merge_logs, invoice_by_customer=invoice_by_customer, closing_entry=closing_entry)
	else:
		create_merge_logs(invoice_by_customer, closing_entry)


def unconsolidate_pos_invoices(closing_entry):
	merge_logs = frappe.get_all(
		"POS Invoice Merge Log", filters={"pos_closing_entry": closing_entry.name}, pluck="name"
	)

	if len(closing_entry.pos_transactions) >= 10:
		closing_entry.set_status(update=True, status="Queued")
		enqueue_job(cancel_merge_logs, merge_logs=merge_logs, closing_entry=closing_entry)
	else:
		cancel_merge_logs(merge_logs, closing_entry)


def split_invoices(invoices):
	"""
	Splits invoices into multiple groups
	Use-case:
	If a serial no is sold and later it is returned
	then split the invoices such that the selling entry is merged first and then the return entry
	"""
	# Input
	# invoices = [
	# 	{'pos_invoice': 'Invoice with SR#1 & SR#2', 'is_return': 0},
	# 	{'pos_invoice': 'Invoice with SR#1', 'is_return': 1},
	# 	{'pos_invoice': 'Invoice with SR#2', 'is_return': 0}
	# ]
	# Output
	# _invoices = [
	# 	[{'pos_invoice': 'Invoice with SR#1 & SR#2', 'is_return': 0}],
	# 	[{'pos_invoice': 'Invoice with SR#1', 'is_return': 1}, {'pos_invoice': 'Invoice with SR#2', 'is_return': 0}],
	# ]

	_invoices = []
	special_invoices = []
	pos_return_docs = [
		frappe.get_cached_doc("POS Invoice", d.pos_invoice)
		for d in invoices
		if d.is_return and d.return_against
	]

	for pos_invoice in pos_return_docs:
		for item in pos_invoice.items:
			if not item.serial_no and not item.serial_and_batch_bundle:
				continue

			return_against_is_added = any(
				d for d in _invoices if d and d[0].pos_invoice == pos_invoice.return_against
			)
			if return_against_is_added:
				break

			return_against_is_consolidated = (
				frappe.db.get_value("POS Invoice", pos_invoice.return_against, "status", cache=True)
				== "Consolidated"
			)
			if return_against_is_consolidated:
				break

			pos_invoice_row = [d for d in invoices if d.pos_invoice == pos_invoice.return_against]
			_invoices.append(pos_invoice_row)
			special_invoices.append(pos_invoice.return_against)
			break

	_invoices.append([d for d in invoices if d.pos_invoice not in special_invoices])

	return _invoices


def create_merge_logs(invoice_by_customer, closing_entry=None):
	try:
		for customer, invoices in invoice_by_customer.items():
			for _invoices in split_invoices(invoices):
				merge_log = frappe.new_doc("POS Invoice Merge Log")
				merge_log.posting_date = (
					getdate(closing_entry.get("posting_date")) if closing_entry else nowdate()
				)
				merge_log.posting_time = (
					get_time(closing_entry.get("posting_time")) if closing_entry else nowtime()
				)
				merge_log.customer = customer
				merge_log.pos_closing_entry = closing_entry.get("name") if closing_entry else None
				merge_log.set("pos_invoices", _invoices)
				merge_log.save(ignore_permissions=True)
				merge_log.submit()
		if closing_entry:
			closing_entry.set_status(update=True, status="Submitted")
			closing_entry.db_set("error_message", "")
			closing_entry.update_opening_entry()

	except Exception as e:
		frappe.db.rollback()
		message_log = frappe.message_log.pop() if frappe.message_log else str(e)
		error_message = get_error_message(message_log)

		if closing_entry:
			closing_entry.set_status(update=True, status="Failed")
			if isinstance(error_message, list):
				error_message = json.dumps(error_message)
			closing_entry.db_set("error_message", error_message)
		raise

	finally:
		frappe.db.commit()
		frappe.publish_realtime("closing_process_complete", user=frappe.session.user)


def cancel_merge_logs(merge_logs, closing_entry=None):
	try:
		for log in merge_logs:
			merge_log = frappe.get_doc("POS Invoice Merge Log", log)
			if merge_log.docstatus == 2:
				continue

			merge_log.flags.ignore_permissions = True
			merge_log.cancel()

		if closing_entry:
			closing_entry.set_status(update=True, status="Cancelled")
			closing_entry.db_set("error_message", "")
			closing_entry.update_opening_entry(for_cancel=True)

	except Exception as e:
		frappe.db.rollback()
		message_log = frappe.message_log.pop() if frappe.message_log else str(e)
		error_message = get_error_message(message_log)

		if closing_entry:
			closing_entry.set_status(update=True, status="Submitted")
			closing_entry.db_set("error_message", error_message)
		raise

	finally:
		frappe.db.commit()
		frappe.publish_realtime("closing_process_complete", user=frappe.session.user)


def enqueue_job(job, **kwargs):
	check_scheduler_status()

	closing_entry = kwargs.get("closing_entry") or {}

	job_id = "pos_invoice_merge::" + str(closing_entry.get("name"))
	if not is_job_enqueued(job_id):
		enqueue(
			job,
			**kwargs,
			queue="long",
			timeout=10000,
			event="processing_merge_logs",
			job_id=job_id,
			now=frappe.conf.developer_mode or frappe.flags.in_test,
		)

		if job == create_merge_logs:
			msg = _("POS Invoices will be consolidated in a background process")
		else:
			msg = _("POS Invoices will be unconsolidated in a background process")

		frappe.msgprint(msg, alert=1)


def check_scheduler_status():
	if is_scheduler_inactive() and not frappe.flags.in_test:
		frappe.throw(_("Scheduler is inactive. Cannot enqueue job."), title=_("Scheduler Inactive"))


def get_error_message(message) -> str:
	try:
		return message["message"]
	except Exception:
		return str(message)


def get_sales_invoice_item(return_against_pos_invoice, pos_invoice_item):
	try:
		SalesInvoice = DocType("Sales Invoice")
		SalesInvoiceItem = DocType("Sales Invoice Item")

		query = (
			frappe.qb.from_(SalesInvoice)
			.from_(SalesInvoiceItem)
			.select(SalesInvoiceItem.name)
			.where(
				(SalesInvoice.name == SalesInvoiceItem.parent)
				& (SalesInvoice.is_return == 0)
				& (SalesInvoiceItem.pos_invoice == return_against_pos_invoice)
				& (SalesInvoiceItem.pos_invoice_item == pos_invoice_item)
			)
		)

		result = query.run(as_dict=True)
		return result[0].name if result else None
	except Exception:
		return None

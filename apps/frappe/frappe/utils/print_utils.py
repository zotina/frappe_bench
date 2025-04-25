from typing import Literal

import frappe


def get_print(
	doctype=None,
	name=None,
	print_format=None,
	style=None,
	as_pdf=False,
	doc=None,
	output=None,
	no_letterhead=0,
	password=None,
	pdf_options=None,
	letterhead=None,
	pdf_generator: Literal["wkhtmltopdf", "chrome"] | None = None,
):
	"""Get Print Format for given document.
	:param doctype: DocType of document.
	:param name: Name of document.
	:param print_format: Print Format name. Default 'Standard',
	:param style: Print Format style.
	:param as_pdf: Return as PDF. Default False.
	:param password: Password to encrypt the pdf with. Default None
	:param pdf_generator: PDF generator to use. Default 'wkhtmltopdf'
	"""

	"""
	local.form_dict.pdf_generator is set from before_request hook (print designer app) for download_pdf endpoint
	if it is not set (internal function call) then set it
	"""
	import copy

	from frappe.utils.pdf import get_pdf
	from frappe.website.serve import get_response_without_exception_handling

	local = frappe.local
	if "pdf_generator" not in local.form_dict:
		# if arg is passed, use that, else get setting from print format
		if pdf_generator is None:
			pdf_generator = (
				frappe.get_cached_value("Print Format", print_format, "pdf_generator") or "wkhtmltopdf"
			)
		local.form_dict.pdf_generator = pdf_generator

	original_form_dict = copy.deepcopy(local.form_dict)
	try:
		local.form_dict.doctype = doctype
		local.form_dict.name = name
		local.form_dict.format = print_format
		local.form_dict.style = style
		local.form_dict.doc = doc
		local.form_dict.no_letterhead = no_letterhead
		local.form_dict.letterhead = letterhead

		pdf_options = pdf_options or {}
		if password:
			pdf_options["password"] = password

		response = get_response_without_exception_handling("printview", 200)
		html = str(response.data, "utf-8")
	finally:
		local.form_dict = original_form_dict

	if not as_pdf:
		return html

	if local.form_dict.pdf_generator != "wkhtmltopdf":
		hook_func = frappe.get_hooks("pdf_generator")
		for hook in hook_func:
			"""
			check pdf_generator value in your hook function.
			if it matches run and return pdf else return None
			"""
			pdf = frappe.call(
				hook,
				print_format=print_format,
				html=html,
				options=pdf_options,
				output=output,
				pdf_generator=local.form_dict.pdf_generator,
			)
			# if hook returns a value, assume it was the correct pdf_generator and return it
			if pdf:
				return pdf

	return get_pdf(html, options=pdf_options, output=output)

import frappe
from frappe import _
from erpnext.controllers.api.utils import validate_jwt
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

@frappe.whitelist(allow_guest=False)
@validate_jwt
def get_purchase_invoice_list():
    """
    REST API endpoint to fetch a list of Purchase Invoices with specific columns.
    Returns: List of Purchase Invoices with Supplier Name, Status, Posting Date, Due Date, Grand Total, Outstanding Amount, ID.
    Example usage:
    http://erpnext.localhost:8000/api/method/erpnext.controllers.api.page.purchase_invoice_api.get_purchase_invoice_list
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        if not frappe.has_permission("Purchase Invoice", "read"):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("You do not have permission to read Purchase Invoice records.")
            return

        purchase_invoices = frappe.get_all(
            "Purchase Invoice",
            fields=[
                "supplier_name",
                "status",
                "posting_date",
                "due_date",
                "grand_total",
                "outstanding_amount",
                "name"
            ],
            filters={},
            order_by="posting_date desc"
        )

        frappe.local.response["status"] = "success"
        frappe.local.response["data"] = purchase_invoices
        return

    except Exception as e:
        frappe.log_error(f"Error fetching Purchase Invoice list: {str(e)}", "Purchase Invoice API")
        frappe.local.response["status"] = "error"
        frappe.local.response["message"] = _("An error occurred while fetching the Purchase Invoice list.")
        return

@frappe.whitelist(allow_guest=False)
@validate_jwt
def pay_purchase_invoice(invoice_name):
    """
    REST API endpoint to mark a Purchase Invoice as Paid by creating a Payment Entry.
    Args:
        invoice_name (str): Name of the Purchase Invoice to pay.
    Returns: Success or error message.
    Example usage:
    http://erpnext.localhost:8000/api/method/erpnext.controllers.api.page.purchase_invoice_api.pay_purchase_invoice?invoice_name=ACC-PINV-2025-00001
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        # Validate permissions
        if not frappe.has_permission("Purchase Invoice", "write"):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("You do not have permission to write Purchase Invoice records.")
            return

        if not frappe.has_permission("Payment Entry", "create"):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("You do not have permission to create Payment Entry records.")
            return

        # Fetch the Purchase Invoice
        if not frappe.db.exists("Purchase Invoice", invoice_name):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Purchase Invoice {0} does not exist.").format(invoice_name)
            return

        invoice = frappe.get_doc("Purchase Invoice", invoice_name)

        # Validate invoice
        if invoice.docstatus != 1:
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Purchase Invoice {0} is not submitted.").format(invoice_name)
            return

        if invoice.outstanding_amount <= 0:
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Purchase Invoice {0} is already paid.").format(invoice_name)
            return

        if invoice.on_hold:
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Purchase Invoice {0} is on hold.").format(invoice_name)
            return

        # Get default payment account from Accounts Settings
        default_bank_account = frappe.db.get_value(
            "Company", invoice.company, "default_bank_account"
        ) or frappe.db.get_single_value("Accounts Settings", "default_payment_account")
        if not default_bank_account:
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("No default bank account set in Company or Accounts Settings.")
            return

        # Create Payment Entry using get_payment_entry
        payment_entry = get_payment_entry("Purchase Invoice", invoice_name)
        payment_entry.paid_from = default_bank_account
        payment_entry.paid_to = invoice.credit_to
        payment_entry.paid_amount = invoice.outstanding_amount
        payment_entry.received_amount = invoice.outstanding_amount
        payment_entry.posting_date = frappe.utils.nowdate()
        payment_entry.reference_no = f"Payment for {invoice_name}"
        payment_entry.reference_date = frappe.utils.nowdate()

        # Insert and submit Payment Entry
        payment_entry.insert()
        payment_entry.submit()

        # Refresh invoice status
        invoice.load_from_db()
        invoice.set_status(update=True)

        frappe.local.response["status"] = "success"
        frappe.local.response["message"] = _("Purchase Invoice {0} marked as Paid.").format(invoice_name)
        frappe.local.response["data"] = {
            "invoice_name": invoice.name,
            "status": invoice.status,
            "outstanding_amount": invoice.outstanding_amount
        }
        return

    except Exception as e:
        frappe.log_error(f"Error paying Purchase Invoice {invoice_name}: {str(e)}", "Purchase Invoice API")
        frappe.local.response["status"] = "error"
        frappe.local.response["message"] = _("An error occurred while paying the Purchase Invoice: {0}").format(str(e))
        return
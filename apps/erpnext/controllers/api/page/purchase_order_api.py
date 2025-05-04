import frappe
from frappe import _
from erpnext.controllers.api.utils import validate_jwt

@frappe.whitelist(allow_guest=False)
@validate_jwt
def get_purchase_order_list(supplier=None):
    """
    REST API endpoint to fetch a list of Purchase Orders with specific columns.
    Args:
        supplier (str, optional): Filter by supplier name.
    Returns: List of Purchase Orders with Supplier, Supplier Name, Status, Transaction Date, Grand Total, Per Billed, Per Received, Received, Paid, ID, and supplier list in metadata.
    Example usage:
    http://erpnext.localhost:8000/api/method/erpnext.controllers.api.page.purchase_order_api.get_purchase_order_list?supplier=SUP-001
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        # Check permissions
        if not frappe.has_permission("Purchase Order", "read"):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("You do not have permission to read Purchase Order records.")
            return

        # Prepare filters
        filters = {}
        if supplier:
            filters["supplier"] = supplier

        # Fetch Purchase Order records
        purchase_orders = frappe.get_all(
            "Purchase Order",
            fields=[
                "supplier",
                "supplier_name",
                "status",
                "transaction_date",
                "grand_total",
                "per_billed",
                "per_received",
                "name"
            ],
            filters=filters,
            order_by="transaction_date desc"
        )

        # Compute 'received' and 'paid' booleans
        for po in purchase_orders:
            # Set received: True if a Purchase Receipt exists for this Purchase Order
            linked_receipts = frappe.get_all(
                "Purchase Receipt Item",
                filters={"purchase_order": po.name, "docstatus": 1},  # Submitted receipts only
                fields=["parent"]
            )
            po["received"] = 1 if linked_receipts else 0

            # Set paid: Check if Purchase Order is linked to a Paid Purchase Invoice
            linked_invoices = frappe.get_all(
                "Purchase Invoice Item",
                filters={"purchase_order": po.name, "docstatus": 1},  # Submitted invoices only
                fields=["parent"]
            )
            invoice_names = [item.parent for item in linked_invoices]
            if invoice_names:
                paid_invoices = frappe.get_all(
                    "Purchase Invoice",
                    filters={"name": ["in", invoice_names], "status": "Paid", "docstatus": 1},
                    fields=["name"]
                )
                po["paid"] = 1 if paid_invoices else 0
            else:
                po["paid"] = 0

        # Fetch list of supplier names
        suppliers = frappe.get_all("Supplier", fields=["name"], order_by="name asc")
        supplier_names = [supplier["name"] for supplier in suppliers]

        frappe.local.response["status"] = "success"
        frappe.local.response["data"] = purchase_orders
        frappe.local.response["metadata"] = {"suppliers": supplier_names}

        return

    except Exception as e:
        frappe.log_error(f"Error fetching Purchase Order list: {str(e)}\n{frappe.get_traceback()}", "Purchase Order API")
        frappe.local.response["status"] = "error"
        frappe.local.response["message"] = _("An error occurred while fetching the Purchase Order list: {0}").format(str(e))
        return

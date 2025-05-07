import frappe
from frappe import _
from erpnext.controllers.api.utils import validate_jwt
@frappe.whitelist(allow_guest=False)
@validate_jwt
def get_request_for_quotation_list(supplier=None):
    """
    REST API endpoint to fetch a list of Request for Quotations with specific columns.
    Args:
        supplier (str, optional): Filter by supplier name.
    Returns: List of Request for Quotations with Title, Status, Date, Grand Total, ID, and supplier list in metadata.
    Example usage:
    http://erpnext.localhost:8000/api/method/erpnext.controllers.api.page.request_for_quotation_api.get_request_for_quotation_list?supplier=SUP-001
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        # Prepare filters
        filters = {}
        if supplier:
            filters["supplier"] = ["like", f"%{supplier}%"]

        # Fetch Request for Quotation records
        rfqs = frappe.get_all(
            "Request for Quotation",
            fields=[
                "name",
                "status",
                "transaction_date",
                "company"
            ],
            filters=filters,
            order_by="transaction_date desc"
        )

        # Fetch suppliers linked to each RFQ
        for rfq in rfqs:
            suppliers = frappe.get_all(
                "Request for Quotation Supplier",
                filters={"parent": rfq["name"]},
                fields=["supplier"]
            )
            rfq["suppliers"] = [s.supplier for s in suppliers]

        # Fetch list of supplier names
        suppliers = frappe.get_all("Supplier", fields=["name"], order_by="name asc")
        supplier_names = [supplier["name"] for supplier in suppliers]

        frappe.local.response["status"] = "success"
        frappe.local.response["data"] = rfqs
        frappe.local.response["metadata"] = {"suppliers": supplier_names}

        return

    except Exception as e:
        print(f"Error fetching Request for Quotation list: {str(e)}", "Request for Quotation API")
        frappe.local.response["status"] = "error"
        frappe.local.response["message"] = _(f"Error fetching Request for Quotation list: {str(e)}", "Request for Quotation API")
        return
    
    
@frappe.whitelist(allow_guest=False)
@validate_jwt
def get_request_for_quotation_item_details(parent):
    """
    REST API endpoint to fetch details of Request for Quotation Items for a specific RFQ.
    Args:
        parent (str): The name of the Request for Quotation (e.g., 'RFQ-2025-00001').
    Returns: List of Request for Quotation Items with item_code, item_name, qty, and name.
    Example usage:
    http://erpnext.localhost:8000/api/method/erpnext.controllers.api.page.request_for_quotation_api.get_request_for_quotation_item_details?parent=RFQ-2025-00001
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        # Validate inputs
        if not parent or not isinstance(parent, str):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Invalid or missing parent parameter. Please provide a valid Request for Quotation ID.")
            return

        # Check if the Request for Quotation exists
        if not frappe.db.exists("Request for Quotation", parent):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Request for Quotation {0} does not exist.").format(parent)
            return

        # Check permissions
        if not frappe.has_permission("Request for Quotation", "read"):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("You do not have permission to read Request for Quotation records.")
            return

        # Fetch Request for Quotation Item records
        items = frappe.get_all(
            "Request for Quotation Item",
            filters={"parent": parent},
            fields=["name", "item_code", "item_name", "qty"]
        )

        if not items:
            frappe.local.response["status"] = "success"
            frappe.local.response["data"] = []
            frappe.local.response["message"] = _("No items found for Request for Quotation {0}.").format(parent)
            return

        frappe.local.response["status"] = "success"
        frappe.local.response["data"] = items

        return

    except Exception as e:
        frappe.log_error(f"Error fetching Request for Quotation Item details: {str(e)}", "Request for Quotation Item API")
        frappe.local.response["status"] = "error"
        frappe.local.response["message"] = _("An error occurred while fetching Request for Quotation Item details.")
        return
    
    
@frappe.whitelist(allow_guest=False)
@validate_jwt
def create_supplier_quotation_from_rfq(rfq_item_id, rate, supplier):
    """
    REST API endpoint to create a Supplier Quotation from a Request for Quotation Item.
    Args:
        rfq_item_id (str): The name of the Request for Quotation Item (e.g., 'RFQI-001').
        rate (float): The rate to set for the item in the Supplier Quotation.
        supplier (str): The supplier for the Supplier Quotation.
    Returns: Success message with the created Supplier Quotation ID or error details.
    Example usage:
    http://erpnext.localhost:8000/api/method/erpnext.controllers.api.page.request_for_quotation_api.create_supplier_quotation_from_rfq?rfq_item_id=RFQI-001&rate=200&supplier=SUP-001
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        # Validate inputs
        if not rfq_item_id or not isinstance(rfq_item_id, str):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Invalid or missing rfq_item_id parameter.")
            return

        if not supplier or not isinstance(supplier, str):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Invalid or missing supplier parameter.")
            return

        try:
            rate = float(rate)
            if rate < 0:
                frappe.local.response["status"] = "error"
                frappe.local.response["message"] = _("Rate must be a non-negative number.")
                return
        except (ValueError, TypeError):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Invalid rate parameter. Please provide a valid number.")
            return

        # Check if the RFQ Item exists
        if not frappe.db.exists("Request for Quotation Item", rfq_item_id):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Request for Quotation Item {0} does not exist.").format(rfq_item_id)
            return

        # Check if the Supplier exists
        if not frappe.db.exists("Supplier", supplier):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Supplier {0} does not exist.").format(supplier)
            return

        # Check permissions
        if not frappe.has_permission("Supplier Quotation", "create"):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("You do not have permission to create Supplier Quotation records.")
            return

        # Fetch the RFQ Item
        rfq_item = frappe.get_doc("Request for Quotation Item", rfq_item_id)
        rfq = frappe.get_doc("Request for Quotation", rfq_item.parent)

        # Create a new Supplier Quotation
        supplier_quotation = frappe.new_doc("Supplier Quotation")
        supplier_quotation.supplier = supplier
        supplier_quotation.transaction_date = frappe.utils.nowdate()
        supplier_quotation.company = rfq.company
        supplier_quotation.request_for_quotation = rfq.name

        # Add the item to the Supplier Quotation
        supplier_quotation.append("items", {
            "item_code": rfq_item.item_code,
            "item_name": rfq_item.item_name,
            "qty": rfq_item.qty,
            "rate": rate,
            "amount": rate * rfq_item.qty,
            "request_for_quotation": rfq.name,
            "request_for_quotation_item": rfq_item.name
        })

        # Save and submit the Supplier Quotation
        supplier_quotation.insert()
        supplier_quotation.submit()
        frappe.db.commit()

        frappe.local.response["status"] = "success"
        frappe.local.response["message"] = _("Successfully created Supplier Quotation {0} from Request for Quotation Item {1}.").format(
            supplier_quotation.name, rfq_item_id
        )
        frappe.local.response["data"] = {"supplier_quotation": supplier_quotation.name}
        return

    except Exception as e:
        frappe.log_error(f"Error creating Supplier Quotation: {str(e)}", "Create Supplier Quotation API")
        frappe.local.response["status"] = "error"
        frappe.local.response["message"] = _("An error occurred while creating the Supplier Quotation: {0}").format(str(e))
        return
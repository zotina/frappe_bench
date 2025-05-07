import frappe
from frappe import _
from erpnext.controllers.api.utils import validate_jwt

@frappe.whitelist(allow_guest=False)
@validate_jwt
def get_supplier_quotation_list(supplier=None, request_for_quotation=None):
    """
    REST API endpoint to fetch a list of Supplier Quotations with specific columns and child items.
    Args:
        supplier (str, optional): Filter by supplier name.
        request_for_quotation (str, optional): Filter by Request for Quotation ID.
    Returns: List of Supplier Quotations with Title, Status, Date, Valid Till, Grand Total, ID, child items, and supplier list in metadata.
    Example usage:
    http://erpnext.localhost:8000/api/method/erpnext.controllers.api.page.supplier_quotation_api.get_supplier_quotation_list?supplier=SUP-001&request_for_quotation=RFQ-2025-00001
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        # Prepare filters for Supplier Quotation
        filters = {}
        if supplier:
            filters["supplier"] = supplier

        # Fetch Supplier Quotation records
        supplier_quotations = frappe.get_all(
            "Supplier Quotation",
            fields=[
                "title",
                "status",
                "transaction_date",
                "valid_till",
                "grand_total",
                "name",
                "supplier"
            ],
            filters=filters,
            order_by="transaction_date desc"
        )

        # Filter by request_for_quotation using Supplier Quotation Item
        if request_for_quotation:
            # Get Supplier Quotation Items linked to the RFQ
            sq_items = frappe.get_all(
                "Supplier Quotation Item",
                filters={"request_for_quotation": request_for_quotation},
                fields=["parent"],
                distinct=True
            )
            # Extract parent Supplier Quotation names
            valid_quotation_names = [item["parent"] for item in sq_items]
            # Filter supplier_quotations to only include those linked to the RFQ
            supplier_quotations = [
                sq for sq in supplier_quotations
                if sq["name"] in valid_quotation_names
            ]

        # Fetch child items for each Supplier Quotation
        for quotation in supplier_quotations:
            child_items = frappe.get_all(
                "Supplier Quotation Item",
                filters={"parent": quotation["name"]},
                fields=[
                    "name",
                    "item_code",
                    "item_name",
                    "qty",
                    "rate",
                    "amount",
                    "request_for_quotation",
                    "request_for_quotation_item"
                ]
            )
            quotation["child"] = child_items

        # Fetch list of supplier names
        suppliers = frappe.get_all("Supplier", fields=["name"], order_by="name asc")
        supplier_names = [supplier["name"] for supplier in suppliers]

        frappe.local.response["status"] = "success"
        frappe.local.response["data"] = supplier_quotations
        frappe.local.response["metadata"] = {"suppliers": supplier_names}

        return

    except Exception as e:
        frappe.log_error(f"Error fetching Supplier Quotation list: {str(e)}", "Supplier Quotation API")
        frappe.local.response["status"] = "error"
        frappe.local.response["message"] = (f"Error fetching Supplier Quotation list: {str(e)}", "Supplier Quotation API")
        return
    
@frappe.whitelist(allow_guest=False)
@validate_jwt
def get_supplier_quotation_item_details(parent):
    """
    REST API endpoint to fetch details of Supplier Quotation Items for a specific Supplier Quotation.
    Args:
        parent (str): The name of the Supplier Quotation (e.g., 'PUR-SQTN-2025-00001').
    Returns: List of Supplier Quotation Items with item_code, item_name, qty, rate, amount, and name.
    Example usage:
    http://erpnext.localhost:8000/api/method/erpnext.controllers.api.page.supplier_quotation_api.get_supplier_quotation_item_details?parent=PUR-SQTN-2025-00001
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        # Validate inputs
        if not parent or     not isinstance(parent, str):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Invalid or missing parent parameter. Please provide a valid Supplier Quotation ID.")
            return

        # Check if the Supplier Quotation exists
        if not frappe.db.exists("Supplier Quotation", parent):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Supplier Quotation {0} does not exist.").format(parent)
            return

        # Check permissions
        if not frappe.has_permission("Supplier Quotation", "read"):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("You do not have permission to read Supplier Quotation records.")
            return

        # Fetch Supplier Quotation Item records
        items = frappe.get_all(
            "Supplier Quotation Item",
            filters={"parent": parent},
            fields=["name", "item_code", "item_name", "qty", "rate", "amount"]
        )

        if not items:
            frappe.local.response["status"] = "success"
            frappe.local.response["data"] = []
            frappe.local.response["message"] = _("No items found for Supplier Quotation {0}.").format(parent)
            return

        frappe.local.response["status"] = "success"
        frappe.local.response["data"] = items

        return

    except Exception as e:
        frappe.log_error(f"Error fetching Supplier Quotation Item details: {str(e)}", "Supplier Quotation Item API")
        frappe.local.response["status"] = "error"
        frappe.local.response["message"] = _("An error occurred while fetching Supplier Quotation Item details.")
        return



@frappe.whitelist(allow_guest=False)
@validate_jwt
def update_supplier_quotation_item_rate(item_id, rate):
    """
    REST API endpoint to update the rate and amount of a specific Supplier Quotation Item.
    Handles Draft, Submitted, and Cancelled Supplier Quotations according to ERPNext workflow:
    - Draft: Updates rate directly and keeps the quotation in Draft status.
    - Submitted: Cancels the quotation, amends the cancelled quotation to create a draft,
                updates the rate, and submits the amended quotation.
    - Cancelled: Creates an amended draft directly, updates the rate, and submits the amended quotation.
    
    Args:
        item_id (str): The name of the Supplier Quotation Item (e.g., 'SQI-001').
        rate (float): The new rate value to set for the item.
    Returns: Success message with updated Supplier Quotation ID or error details.
    Example usage:
    http://erpnext.localhost:8000/api/method/erpnext.controllers.api.page.supplier_quotation_api.update_supplier_quotation_item_rate?item_id=SQI-001&rate=200
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        # Validate inputs
        if not item_id or not isinstance(item_id, str):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Invalid or missing item_id parameter. Please provide a valid Supplier Quotation Item ID.")
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

        # Check if the Supplier Quotation Item exists
        if not frappe.db.exists("Supplier Quotation Item", item_id):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Supplier Quotation Item {0} does not exist.").format(item_id)
            return

        # Check permissions
        if not frappe.has_permission("Supplier Quotation", "write"):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("You do not have permission to update Supplier Quotation records.")
            return

        # Check submit permission for amended quotation
        if not frappe.has_permission("Supplier Quotation", "submit"):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("You do not have permission to submit Supplier Quotation records.")
            return

        # Check cancel permission for submitted quotation
        if not frappe.has_permission("Supplier Quotation", "cancel"):
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("You do not have permission to cancel Supplier Quotation records.")
            return

        # Fetch the Supplier Quotation Item
        item = frappe.get_doc("Supplier Quotation Item", item_id)
        parent = item.parent

        # Load the parent Supplier Quotation
        supplier_quotation = frappe.get_doc("Supplier Quotation", parent)

        if supplier_quotation.status == "Draft":
            # Direct update for Draft status
            frappe.db.set_value(
                "Supplier Quotation Item",
                item_id,
                {
                    "rate": rate,
                    "amount": rate * item.qty
                }
            )
            supplier_quotation.run_method("calculate_taxes_and_totals")
            supplier_quotation.db_update()
            frappe.db.commit()

            frappe.local.response["status"] = "success"
            frappe.local.response["message"] = _("Successfully updated rate for Supplier Quotation Item {0} in Supplier Quotation {1}.").format(item_id, parent)
            frappe.local.response["data"] = {"supplier_quotation": parent}
            return

        elif supplier_quotation.status == "Submitted":
            # Check if linked to Purchase Order
            linked_purchase_orders = frappe.get_all(
                "Purchase Order Item",
                filters={"supplier_quotation": parent},
                fields=["parent"]
            )

            # Check if linked Purchase Orders are referenced in Purchase Invoices
            linked_purchase_invoices = []
            if linked_purchase_orders:
                purchase_order_names = [po.parent for po in linked_purchase_orders]
                linked_purchase_invoices = frappe.get_all(
                    "Purchase Invoice Item",
                    filters={"purchase_order": ["in", purchase_order_names]},
                    fields=["parent"]
                )

            if linked_purchase_orders or linked_purchase_invoices:
                linked_docs = []
                if linked_purchase_orders:
                    linked_docs.extend([po.parent for po in linked_purchase_orders])
                if linked_purchase_invoices:
                    linked_docs.extend([pi.parent for pi in linked_purchase_invoices])
                frappe.local.response["status"] = "error"
                frappe.local.response["message"] = _("Cannot amend Supplier Quotation {0} as it is linked to {1}.").format(
                    parent, ", ".join(set(linked_docs))  # Use set to avoid duplicate document names
                )
                return

            # Cancel the Supplier Quotation
            supplier_quotation.cancel()
            frappe.db.commit()  # Commit cancellation

        elif supplier_quotation.status != "Cancelled":
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Supplier Quotation {0} is in {1} status. Only Draft, Submitted, or Cancelled quotations can be updated.").format(
                parent, supplier_quotation.status
            )
            return

        # Amend the cancelled Supplier Quotation (for Submitted or Cancelled status)
        amended_quotation = frappe.copy_doc(supplier_quotation)
        amended_quotation.amended_from = parent
        amended_quotation.status = "Draft"
        # Clear the name to let ERPNext generate a unique name
        amended_quotation.name = None
        amended_quotation.insert()

        # Find the corresponding item in the amended quotation
        for amended_item in amended_quotation.items:
            if amended_item.item_code == item.item_code and amended_item.qty == item.qty:
                amended_item.rate = rate
                amended_item.amount = rate * amended_item.qty
                break
        else:
            frappe.local.response["status"] = "error"
            frappe.local.response["message"] = _("Item {0} not found in amended Supplier Quotation.").format(item_id)
            return

        # Recalculate taxes and totals
        amended_quotation.run_method("calculate_taxes_and_totals")
        amended_quotation.save()

        # Submit the amended quotation
        amended_quotation.submit()
        frappe.db.commit()

        frappe.local.response["status"] = "success"
        frappe.local.response["message"] = _("Successfully amended and submitted Supplier Quotation {0} with updated rate for item {1} in new Supplier Quotation {2}.").format(
            parent, item_id, amended_quotation.name
        )
        frappe.local.response["data"] = {"supplier_quotation": amended_quotation.name}
        return

    except Exception as e:
        frappe.log_error(f"Error updating Supplier Quotation Item: {str(e)}", "Supplier Quotation Item API")
        frappe.local.response["status"] = "error"
        frappe.local.response["message"] = _("An error occurred while updating the Supplier Quotation Item: {0}").format(str(e))
        return
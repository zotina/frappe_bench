import frappe
import csv
from io import StringIO

def create_supplier(supplier_data):
    """
    Create a Supplier in ERPNext if it doesn't exist.
    
    Args:
        supplier_data (dict): Dictionary containing supplier details, e.g.,
                             {'supplier_name': 'SUP001', 'supplier_group': 'All Supplier Groups'}
    
    Returns:
        str: Name of the created or existing Supplier.
    """
    try:
        supplier_name = supplier_data.get("supplier_name")
        if frappe.db.exists("Supplier", supplier_name):
            return supplier_name
        
        supplier_doc = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": supplier_name,
            "supplier_group": supplier_data.get("supplier_group", "All Supplier Groups"),
            "supplier_type": "Company"
        })
        supplier_doc.insert(ignore_permissions=False)
        frappe.db.commit()
        return supplier_doc.name
    except Exception as e:
        frappe.log_error(f"Error creating Supplier: {str(e)}")
        raise

def create_company(company_data):
    """
    Create a Company in ERPNext if it doesn't exist, including Chart of Accounts.
    
    Args:
        company_data (dict): Dictionary containing company details, e.g.,
                            {'company_name': '_Test Company', 'abbr': '_TC'}
    
    Returns:
        str: Name of the created or existing Company.
    """
    try:
        company_name = company_data.get("company_name")
        if frappe.db.exists("Company", company_name):
            return company_name
        
        company_doc = frappe.get_doc({
            "doctype": "Company",
            "company_name": company_name,
            "abbr": company_data.get("abbr", company_name.replace(" ", "_")),
            "default_currency": company_data.get("default_currency", "USD"),
            "country": company_data.get("country", "United States")
        })
        company_doc.insert(ignore_permissions=False)
        
        # Set up Chart of Accounts
        frappe.get_doc({
            "doctype": "Account",
            "account_name": "Creditors",
            "company": company_name,
            "parent_account": "",
            "account_type": "Payable",
            "is_group": 0
        }).insert(ignore_permissions=False)
        
        frappe.get_doc({
            "doctype": "Account",
            "account_name": "Cost of Goods Sold",
            "company": company_name,
            "parent_account": "",
            "account_type": "Expense Account",
            "is_group": 0
        }).insert(ignore_permissions=False)
        
        frappe.db.commit()
        return company_doc.name
    except Exception as e:
        frappe.log_error(f"Error creating Company: {str(e)}")
        raise

def create_item(item_data):
    """
    Create an Item in ERPNext, assuming Item Group and UOM exist.
    
    Args:
        item_data (dict): Dictionary containing item details, e.g., 
                         {'item_code': 'ITEM001', 'item_name': 'Test Item', 
                          'item_group': 'Products', 'is_stock_item': 1}
    
    Returns:
        str: Name of the created Item or raises an exception on failure.
    """
    try:
        # Check if item already exists
        if frappe.db.exists("Item", item_data.get("item_code")):
            return item_data.get("item_code")
        
        # Create new Item document
        item_doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_data.get("item_code"),
            "item_name": item_data.get("item_name", item_data.get("item_code")),
            "item_group": item_data.get("item_group", "Products"),
            "is_stock_item": item_data.get("is_stock_item", 1),
            "stock_uom": item_data.get("stock_uom", "Unit"),
            "description": item_data.get("description", ""),
        })
        
        item_doc.insert(ignore_permissions=False)
        frappe.db.commit()
        return item_doc.name
    except Exception as e:
        frappe.log_error(f"Error creating Item: {str(e)}")
        raise

def create_material_request(mr_data):
    """
    Create a Material Request in ERPNext, assuming Items and UOM exist.
    
    Args:
        mr_data (dict): Dictionary containing Material Request details, e.g.,
                        {'material_request_type': 'Purchase', 
                         'transaction_date': '2025-05-03',
                         'items': [{'item_code': 'ITEM001', 'qty': 10}]}
    
    Returns:
        str: Name of the created Material Request or raises an exception.
    """
    try:
        mr_doc = frappe.get_doc({
            "doctype": "Material Request",
            "material_request_type": mr_data.get("material_request_type", "Purchase"),
            "transaction_date": mr_data.get("transaction_date"),
            "items": [
                {
                    "item_code": item.get("item_code"),
                    "qty": item.get("qty"),
                    "uom": item.get("uom", "Unit"),
                    "schedule_date": mr_data.get("transaction_date")
                } for item in mr_data.get("items", [])
            ]
        })
        
        mr_doc.insert(ignore_permissions=False)
        mr_doc.submit()
        frappe.db.commit()
        return mr_doc.name
    except Exception as e:
        frappe.log_error(f"Error creating Material Request: {str(e)}")
        raise

def create_supplier_quotation(sq_data):
    """
    Create a Supplier Quotation in ERPNext, assuming Supplier, Items, and UOM exist.
    
    Args:
        sq_data (dict): Dictionary containing Supplier Quotation details, e.g.,
                        {'supplier': 'SUP001', 'transaction_date': '2025-05-03',
                         'material_request': 'MR/00001',
                         'items': [{'item_code': 'ITEM001', 'qty': 10, 'rate': 100}]}
    
    Returns:
        str: Name of the created Supplier Quotation or raises an exception.
    """
    try:
        sq_doc = frappe.get_doc({
            "doctype": "Supplier Quotation",
            "supplier": sq_data.get("supplier"),
            "transaction_date": sq_data.get("transaction_date"),
            "material_request": sq_data.get("material_request", ""),
            "items": [
                {
                    "item_code": item.get("item_code"),
                    "qty": item.get("qty"),
                    "rate": item.get("rate"),
                    "uom": item.get("uom", "Unit")
                } for item in sq_data.get("items", [])
            ]
        })
        
        sq_doc.insert(ignore_permissions=False)
        sq_doc.submit()
        frappe.db.commit()
        return sq_doc.name
    except Exception as e:
        frappe.log_error(f"Error creating Supplier Quotation: {str(e)}")
        raise

def create_purchase_order(po_data):
    """
    Create a Purchase Order in ERPNext, assuming Supplier, Items, and UOM exist.
    
    Args:
        po_data (dict): Dictionary containing Purchase Order details, e.g.,
                        {'supplier': 'SUP001', 'transaction_date': '2025-05-03',
                         'supplier_quotation': 'SQT/00001',
                         'items': [{'item_code': 'ITEM001', 'qty': 10, 'rate': 100}]}
    
    Returns:
        str: Name of the created Purchase Order or raises an exception.
    """
    try:
        po_doc = frappe.get_doc({
            "doctype": "Purchase Order",
            "supplier": po_data.get("supplier"),
            "transaction_date": po_data.get("transaction_date"),
            "supplier_quotation": po_data.get("supplier_quotation", ""),
            "items": [
                {
                    "item_code": item.get("item_code"),
                    "qty": item.get("qty"),
                    "rate": item.get("rate"),
                    "uom": item.get("uom", "Unit")
                } for item in po_data.get("items", [])
            ]
        })
        
        po_doc.insert(ignore_permissions=False)
        po_doc.submit()
        frappe.db.commit()
        return po_doc.name
    except Exception as e:
        frappe.log_error(f"Error creating Purchase Order: {str(e)}")
        raise

def create_purchase_invoice(pi_data):
    """
    Create a Purchase Invoice in ERPNext, assuming Supplier, Items, Company, Accounts, and UOM exist.
    
    Args:
        pi_data (dict): Dictionary containing Purchase Invoice details, e.g.,
                        {'supplier': 'SUP001', 'posting_date': '2025-05-03',
                         'purchase_order': 'PO/00001',
                         'items': [{'item_code': 'ITEM001', 'qty': 10, 'rate': 100}],
                         'credit_to': 'Creditors - _TC', 'company': '_Test Company'}
    
    Returns:
        str: Name of the created Purchase Invoice or raises an exception.
    """
    try:
        pi_doc = frappe.get_doc({
            "doctype": "Purchase Invoice",
            "supplier": pi_data.get("supplier"),
            "posting_date": pi_data.get("posting_date"),
            "company": pi_data.get("company", "_Test Company"),
            "purchase_order": pi_data.get("purchase_order", ""),
            "credit_to": pi_data.get("credit_to", "Creditors - _TC"),
            "items": [
                {
                    "item_code": item.get("item_code"),
                    "qty": item.get("qty"),
                    "rate": item.get("rate"),
                    "uom": item.get("uom", "Unit"),
                    "expense_account": pi_data.get("expense_account", f"Cost of Goods Sold - _TC")
                } for item in pi_data.get("items", [])
            ]
        })
        
        pi_doc.insert(ignore_permissions=False)
        pi_doc.submit()
        frappe.db.commit()
        return pi_doc.name
    except Exception as e:
        frappe.log_error(f"Error creating Purchase Invoice: {str(e)}")
        raise

def import_scenario_from_csv(csv_data):
    """
    Import ERPNext scenario data from a CSV string, explicitly creating dependencies.
    
    Args:
        csv_data (str): CSV string with columns for Item, Material Request, etc.
    
    Returns:
        dict: Dictionary of created document names.
    """
    result = {
        "item": None,
        "material_request": None,
        "supplier_quotation": None,
        "purchase_order": None,
        "purchase_invoice": None
    }
    
    try:
        # Parse CSV
        csv_file = StringIO(csv_data)
        reader = csv.DictReader(csv_file)
        for row in reader:
            # Step 1: Create dependencies
            # Create Supplier
            supplier_data = {
                "supplier_name": row.get("supplier"),
                "supplier_group": row.get("supplier_group", "All Supplier Groups")
            }
            create_supplier(supplier_data)
            
            # Create Company
            company_data = {
                "company_name": row.get("company", "_Test Company"),
                "abbr": row.get("abbr", "_TC")
            }
            create_company(company_data)
            
            # Create Item
            item_data = {
                "item_code": row.get("item_code"),
                "item_name": row.get("item_name"),
                "item_group": row.get("item_group", "Products"),
                "is_stock_item": int(row.get("is_stock_item", 1)),
                "stock_uom": row.get("stock_uom", "Unit")
            }
            result["item"] = create_item(item_data)
            
            # Step 2: Create Material Request
            mr_data = {
                "material_request_type": row.get("material_request_type", "Purchase"),
                "transaction_date": row.get("transaction_date"),
                "items": [{"item_code": row.get("item_code"), "qty": float(row.get("qty"))}]
            }
            result["material_request"] = create_material_request(mr_data)
            
            # Step 3: Create Supplier Quotation
            sq_data = {
                "supplier": row.get("supplier"),
                "transaction_date": row.get("transaction_date"),
                "material_request": result["material_request"],
                "items": [{"item_code": row.get("item_code"), "qty": float(row.get("qty")), "rate": float(row.get("rate"))}]
            }
            result["supplier_quotation"] = create_supplier_quotation(sq_data)
            
            # Step 4: Create Purchase Order
            po_data = {
                "supplier": row.get("supplier"),
                "transaction_date": row.get("transaction_date"),
                "supplier_quotation": result["supplier_quotation"],
                "items": [{"item_code": row.get("item_code"), "qty": float(row.get("qty")), "rate": float(row.get("rate"))}]
            }
            result["purchase_order"] = create_purchase_order(po_data)
            
            # Step 5: Create Purchase Invoice
            pi_data = {
                "supplier": row.get("supplier"),
                "posting_date": row.get("posting_date"),
                "company": row.get("company", "_Test Company"),
                "purchase_order": result["purchase_order"],
                "credit_to": row.get("credit_to", "Creditors - _TC"),
                "expense_account": row.get("expense_account", "Cost of Goods Sold - _TC"),
                "items": [{"item_code": row.get("item_code"), "qty": float(row.get("qty")), "rate": float(row.get("rate"))}]
            }
            result["purchase_invoice"] = create_purchase_invoice(pi_data)
        return result
    
    except Exception as e:
        print(f"Error parsing CSV: {str(e)}")
        
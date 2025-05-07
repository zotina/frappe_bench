from erpnext.utilities.country_normalizer import CountryNormalizer
import frappe
from frappe import _
from erpnext.buying.doctype.request_for_quotation.request_for_quotation import make_supplier_quotation_from_rfq
from erpnext.buying.doctype.supplier_quotation.supplier_quotation import make_purchase_order as sq_make_purchase_order
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice as pr_make_purchase_invoice
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

# Modified create_item to handle item_group creation
@frappe.whitelist()
def create_item(data):
    try:
        required_fields = ["item_code", "item_name", "item_group"]
        for field in required_fields:
            if not data.get(field):
                frappe.throw(_(f"Champ requis manquant: {field}"))

        # Check if item_group exists, create if it doesn't
        if not frappe.db.exists("Item Group", data["item_group"]):
            item_group = frappe.get_doc({
                "doctype": "Item Group",
                "item_group_name": data["item_group"],
                "parent_item_group": "All Item Groups"
            })
            item_group.insert()
            frappe.db.commit()

        item = frappe.get_doc({
            "doctype": "Item",
            "name": data.get("name") or frappe.generate_hash(length=10),
            "item_code": data["item_code"],
            "item_name": data["item_name"],
            "item_group": data["item_group"],
            "is_stock_item": 0,
            "stock_uom": "Nos"
        })
        item.insert()
        frappe.db.commit()
        frappe.msgprint(_(f"Item {item.name} créé avec succès"))
        return item.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création de l'Item: {str(e)}"))

@frappe.whitelist()
def create_supplier_group(data):
    try:
        supplier_group = frappe.get_doc({
            "doctype": "Supplier Group",
            "name": data.get("name") or frappe.generate_hash("Supplier Group", 10),
            "supplier_group_name": data.get("name") or "Default Group"
        })
        supplier_group.insert()
        frappe.db.commit()
        frappe.msgprint(_(f"Supplier Group {supplier_group.name} créé avec succès"))
        return supplier_group.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création du Supplier Group: {str(e)}"))

@frappe.whitelist()
def create_supplier(data):
    try:
        required_fields = ["supplier_name", "type", "country"]
        for field in required_fields:
            if not data.get(field):
                frappe.throw(_(f"Champ requis manquant: {field}"))

        # Validate supplier_type
        supplier_type = data.get("type")
        if supplier_type not in ["Company", "Individual"]:
            frappe.throw(_("Le type de fournisseur doit être 'Company' ou 'Individual'"))

        # Normalize country name using CountryNormalizer
        country = CountryNormalizer.normalize_country(data.get("country"))

        # Check if country exists, create if it doesn't
        if not frappe.db.exists("Country", country):
            country_doc = frappe.get_doc({
                "doctype": "Country",
                "country_name": country
            })
            country_doc.insert()
            frappe.db.commit()
            frappe.msgprint(_(f"Country {country} créé avec succès"))

        supplier = frappe.get_doc({
            "doctype": "Supplier",
            "name": data.get("name") or frappe.generate_hash("Supplier", 10),
            "supplier_name": data["supplier_name"],
            "supplier_group": "General",
            "supplier_type": supplier_type,
            "country": country
        })
        supplier.insert()
        frappe.db.commit()
        frappe.msgprint(_(f"Supplier {supplier.name} créé avec succès"))
        return supplier.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création du Supplier: {str(e)}"))

# Modified create_material_request to handle all required fields
@frappe.whitelist()
def create_material_request(data):
    try:
        required_fields = ["material_request_type", "transaction_date", "items"]
        for field in required_fields:
            if not data.get(field):
                frappe.throw(_(f"Champ requis manquant: {field}"))

        # Check if target_warehouse exists, create if it doesn't
        target_warehouse = data.get("target_warehouse")
        if target_warehouse and not frappe.db.exists("Warehouse", target_warehouse):
            warehouse_doc = frappe.get_doc({
                "doctype": "Warehouse",
                "warehouse_name": target_warehouse,
                "is_group": 0,
                "parent_warehouse": "All Warehouses"
            })
            warehouse_doc.insert()
            frappe.db.commit()
            frappe.msgprint(_(f"Warehouse {target_warehouse} créé avec succès"))

        mr = frappe.get_doc({
            "doctype": "Material Request",
            "name": data.get("name") or data.get("ref") or frappe.generate_hash("Material Request", 10),
            "material_request_type": data["material_request_type"],
            "transaction_date": data["transaction_date"],
            "schedule_date": data.get("schedule_date") or data["transaction_date"],
            "status": data.get("status", "Draft"),
            "set_warehouse": target_warehouse,
            "items": [
                {
                    "item_code": item["item_code"],
                    "qty": item["qty"],
                    "schedule_date": data.get("schedule_date") or data["transaction_date"]
                } for item in data["items"]
            ]
        })
        mr.insert()
        mr.submit() if data.get("status") == "Submitted" else mr.save()
        frappe.db.commit()
        frappe.msgprint(_(f"Material Request {mr.name} créé avec succès"))
        return mr.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création du Material Request: {str(e)}"))

        
# New function to process csv3 data
@frappe.whitelist()
def process_csv3_data(records):
    try:
        result = {}
        for record in records:
            ref = record.get("ref_request_quotation")
            supplier = record.get("supplier")
            
            if not frappe.db.exists("Material Request", ref):
                frappe.throw(_(f"Material Request {ref} n'existe pas"))

            if ref not in result:
                result[ref] = []
            if supplier and supplier not in result[ref]:
                result[ref].append(supplier)
        
        return [{"ref_request_quotation": k, "suppliers": v} for k, v in result.items()]
    except Exception as e:
        frappe.throw(_(f"Erreur lors du traitement des données csv3: {str(e)}"))


@frappe.whitelist()
def create_request_for_quotation_from_mr(mr_name, supplier_names):
    try:
        if not frappe.db.exists("Material Request", mr_name):
            frappe.throw(_(f"Material Request {mr_name} n'existe pas"))

        for supplier in supplier_names:
            if not frappe.db.exists("Supplier", supplier):
                frappe.throw(_(f"Supplier {supplier} n'existe pas"))

        mr = frappe.get_doc("Material Request", mr_name)
        rfq = frappe.get_doc({
            "doctype": "Request for Quotation",
            "transaction_date": frappe.utils.nowdate(),
            "status": "Draft",
            "message_for_supplier": "Please provide your best quote.",
            "items": [
                {
                    "item_code": item.item_code,
                    "qty": item.qty,
                    "uom": item.uom or frappe.db.get_value("Item", item.item_code, "stock_uom"),
                    "conversion_factor": 1.0,
                    "material_request": mr_name
                } for item in mr.items
            ],
            "suppliers": [
                {
                    "supplier": supplier
                } for supplier in supplier_names
            ]
        })
        rfq.insert()
        rfq.submit()
        frappe.db.commit()
        frappe.msgprint(_(f"Request for Quotation {rfq.name} créé avec succès"))
        return rfq.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création du Request for Quotation: {str(e)}"))

@frappe.whitelist()
def create_supplier_quotation_from_rfq(rfq_name, supplier, items):
    try:
        if not frappe.db.exists("Request for Quotation", rfq_name):
            frappe.throw(_(f"Request for Quotation {rfq_name} n'existe pas"))
        if not frappe.db.exists("Supplier", supplier):
            frappe.throw(_(f"Supplier {supplier} n'existe pas"))

        sq = make_supplier_quotation_from_rfq(source_name=rfq_name, for_supplier=supplier)
        sq.transaction_date = frappe.utils.nowdate()
        sq.valid_till = frappe.utils.add_days(frappe.utils.nowdate(), 30)

        # Update items with provided qty, rate, uom, and conversion_factor
        for sq_item in sq.items:
            for item in items:
                if sq_item.item_code == item["item_code"]:
                    sq_item.qty = item["qty"]
                    sq_item.rate = item["rate"]
                    sq_item.uom = frappe.db.get_value("Item", item["item_code"], "stock_uom")
                    sq_item.conversion_factor = 1.0
                    break

        sq.insert()
        sq.submit()
        frappe.db.commit()
        frappe.msgprint(_(f"Supplier Quotation {sq.name} créé avec succès"))
        return sq.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création du Supplier Quotation: {str(e)}"))

@frappe.whitelist()
def create_purchase_order_from_sq(sq_name):
    try:
        if not frappe.db.exists("Supplier Quotation", sq_name):
            frappe.throw(_(f"Supplier Quotation {sq_name} n'existe pas"))

        po = sq_make_purchase_order(source_name=sq_name)
        po.transaction_date = frappe.utils.nowdate()
        po.schedule_date = frappe.utils.nowdate()
        for item in po.items:
            item.schedule_date = frappe.utils.nowdate()
        po.insert()
        po.submit()
        frappe.db.commit()
        frappe.msgprint(_(f"Purchase Order {po.name} créé avec succès"))
        return po.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création du Purchase Order: {str(e)}"))

@frappe.whitelist()
def create_purchase_receipt_from_po(po_name):
    try:
        if not frappe.db.exists("Purchase Order", po_name):
            frappe.throw(_(f"Purchase Order {po_name} n'existe pas"))

        po = frappe.get_doc("Purchase Order", po_name)
        pr = frappe.get_doc({
            "doctype": "Purchase Receipt",
            "supplier": po.supplier,
            "posting_date": frappe.utils.nowdate(),
            "status": "Draft",
            "items": [
                {
                    "item_code": item.item_code,
                    "qty": item.qty,
                    "purchase_order": po_name
                } for item in po.items
            ]
        })
        pr.insert()
        pr.submit()
        frappe.db.commit()
        frappe.msgprint(_(f"Purchase Receipt {pr.name} créé avec succès"))
        return pr.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création du Purchase Receipt: {str(e)}"))

@frappe.whitelist()
def create_purchase_invoice_from_pr(pr_name):
    try:
        if not frappe.db.exists("Purchase Receipt", pr_name):
            frappe.throw(_(f"Purchase Receipt {pr_name} n'existe pas"))

        pi = pr_make_purchase_invoice(source_name=pr_name)
        pi.posting_date = frappe.utils.nowdate()
        pi.insert()
        pi.submit()
        frappe.db.commit()
        frappe.msgprint(_(f"Purchase Invoice {pi.name} créé avec succès"))
        return pi.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création du Purchase Invoice: {str(e)}"))

@frappe.whitelist()
def create_payment_entry_from_pi(pi_name, paid_amount, reference_no):
    try:
        if not frappe.db.exists("Purchase Invoice", pi_name):
            frappe.throw(_(f"Purchase Invoice {pi_name} n'existe pas"))

        pe = get_payment_entry(dt="Purchase Invoice", dn=pi_name)
        pe.posting_date = frappe.utils.nowdate()
        pe.paid_amount = paid_amount
        pe.received_amount = paid_amount
        pe.reference_no = reference_no
        pe.insert()
        pe.submit()
        frappe.db.commit()
        frappe.msgprint(_(f"Payment Entry {pe.name} créé avec succès"))
        return pe.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création du Payment Entry: {str(e)}"))

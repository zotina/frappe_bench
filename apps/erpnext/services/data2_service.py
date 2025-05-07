import frappe
import base64
from io import StringIO
from erpnext.services.CsvService import CsvService
from erpnext.utilities.country_normalizer import CountryNormalizer
from frappe.utils import getdate
from frappe import _

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
        frappe.msgprint(_(f"Item {item.name} créé avec succès"))
        return item.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création de l'Item: {str(e)}"))

@frappe.whitelist()
def create_supplier(data):
    try:
        # Log input data for debugging
        print(f"create_supplier input: {data}", "Debug create_supplier")

        required_fields = ["supplier_name", "type", "country"]
        for field in required_fields:
            if not data.get(field):
                frappe.throw(_(f"Champ requis manquant: {field}"))

        # Validate supplier_type
        supplier_type = data.get("type")
        if supplier_type not in ["Company", "Individual"]:
            frappe.throw(_("Le type de fournisseur doit être 'Company' ou 'Individual'"))

        # Check for existing supplier to avoid duplicates
        if frappe.db.exists("Supplier", {"supplier_name": data["supplier_name"]}):
            supplier_name = frappe.db.get_value("Supplier", {"supplier_name": data["supplier_name"]}, "name")
            frappe.msgprint(_(f"Supplier {data['supplier_name']} existe déjà: {supplier_name}"))
            return supplier_name

        # Normalize country name using CountryNormalizer
        from erpnext.utilities.country_normalizer import CountryNormalizer
        country = CountryNormalizer.normalize_country(data.get("country"))
        print(f"Normalized country: {country}", "Debug create_supplier")

        # Check if country exists, create if it doesn't
        if not frappe.db.exists("Country", country):
            country_doc = frappe.get_doc({
                "doctype": "Country",
                "country_name": country
            })
            country_doc.insert()

            frappe.msgprint(_(f"Country {country} créé avec succès"))

        # Get currency using frappe.geo.country_info
        from frappe.geo.country_info import get_country_info
        country_info = get_country_info(country)
        currency = country_info.get("currency")  # e.g., "MGA", "USD"
        currency_name = country_info.get("currency")  # e.g., "Malagasy Ariary", "US Dollar"
        print(f"get_country_info for {country}: {country_info}", "Debug create_supplier")

        # Fallback to company default currency if no currency is found
        if not currency:
            company = frappe.defaults.get_user_default("company") or frappe.db.get_single_value("Global Defaults", "default_company")
            if not company:
                frappe.throw(_("Aucune entreprise par défaut configurée. Veuillez définir une entreprise dans les paramètres."))
            currency = frappe.db.get_value("Company", company, "default_currency")
            currency_name = currency  # Fallback name
            if not currency:
                print(f"No currency found for country {country} and no company default currency", "Debug create_supplier")
                frappe.throw(_(f"Aucune devise trouvée pour le pays {country} ni pour l'entreprise par défaut."))
            print(f"No currency found for country {country}, using company default: {currency}", "Debug create_supplier")

        # Create currency if it doesn't exist in the Currency doctype
        if not frappe.db.exists("Currency", currency):
            print(f"Creating currency {currency} for country {country}", "Debug create_supplier")
            currency_doc = frappe.get_doc({
                "doctype": "Currency",
                "name": currency,
                "currency_name": currency_name or currency
            })
            currency_doc.insert()

            frappe.msgprint(_(f"Currency {currency} créé avec succès"))

        # Ensure Currency Exchange record exists
        from erpnext.utilities.currency_exchange_manager import CurrencyExchangeManager
        company_currency = frappe.db.get_value("Company", frappe.defaults.get_user_default("company"), "default_currency")
        if currency != company_currency:
            exchange_rate = CurrencyExchangeManager.ensure_currency_exchange(
                from_currency=currency,
                to_currency=company_currency,
                date=frappe.utils.nowdate()
            )
            print(
                f"Currency Exchange for {currency} to {company_currency} ensured with rate {exchange_rate}",
                "Debug create_supplier"
            )

        supplier = frappe.get_doc({
            "doctype": "Supplier",
            "name": data.get("name") or frappe.generate_hash("Supplier", 10),
            "supplier_name": data["supplier_name"],
            "supplier_group": "General",
            "supplier_type": supplier_type,
            "country": country,
            "default_currency": currency  # Set the default currency
        })
        supplier.insert()
        frappe.msgprint(_(f"Supplier {supplier.name} créé avec succès"))
        return supplier.name
    except Exception as e:
        frappe.db.rollback()
        print(f"Failed to create Supplier with name {data.get('supplier_name', 'unknown')}: {str(e)}", "Supplier Creation")
        frappe.throw(_(f"Erreur lors de la création du Supplier: {str(e)}"))
                        
@frappe.whitelist()
def create_material_request(data):
    try:
        required_fields = ["material_request_type", "transaction_date", "items"]
        for field in required_fields:
            if not data.get(field):
                frappe.throw(_(f"Champ requis manquant: {field}"))

        # Get the default company and its abbreviation
        company = frappe.defaults.get_user_default("company") or frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            frappe.throw(_("Aucune entreprise par défaut configurée. Veuillez définir une entreprise dans les paramètres."))
        company_abbr = frappe.db.get_value("Company", company, "abbr")
        if not company_abbr:
            frappe.throw(_(f"Aucune abréviation définie pour l'entreprise {company}. Veuillez configurer l'abréviation dans les paramètres de l'entreprise."))

        # Get target warehouse from data
        target_warehouse = data.get("target_warehouse")
        if not target_warehouse:
            frappe.throw(_("Aucun entrepôt cible spécifié dans les données."))

        # Construct warehouse names with company abbreviation
        target_warehouse_with_company = f"{target_warehouse} - {company_abbr}"
        parent_warehouse = f"All Warehouses - {company_abbr}"

        # Find or create a parent group warehouse
        if not frappe.db.exists("Warehouse", parent_warehouse):
            try:
                parent_doc = frappe.get_doc({
                    "doctype": "Warehouse",
                    "warehouse_name": "All Warehouses",
                    "is_group": 1,
                    "company": company
                })
                parent_doc.insert()
    
                frappe.msgprint(_(f"Parent Warehouse {parent_warehouse} créé avec succès"))
            except frappe.DuplicateEntryError:
                frappe.db.rollback()
                if not frappe.db.exists("Warehouse", parent_warehouse):
                    print(f"Failed to create parent warehouse {parent_warehouse} after duplicate error", "Warehouse Creation")
                    frappe.throw(_(f"Impossible de créer l'entrepôt parent {parent_warehouse}"))
            except Exception as e:
                print(f"Failed to create parent warehouse {parent_warehouse}: {str(e)}", "Warehouse Creation")
                frappe.throw(_(f"Impossible de créer l'entrepôt parent {parent_warehouse}: {str(e)}"))

        # Create target warehouse if it doesn't exist
        if not frappe.db.exists("Warehouse", target_warehouse_with_company):
            try:
                warehouse_doc = frappe.get_doc({
                    "doctype": "Warehouse",
                    "warehouse_name": target_warehouse,
                    "is_group": 0,
                    "parent_warehouse": parent_warehouse,
                    "company": company
                })
                warehouse_doc.insert()
    
                frappe.msgprint(_(f"Warehouse {target_warehouse_with_company} créé avec succès"))
            except frappe.DuplicateEntryError:
                frappe.db.rollback()
                if not frappe.db.exists("Warehouse", target_warehouse_with_company):
                    print(f"Failed to create target warehouse {target_warehouse_with_company} after duplicate error", "Warehouse Creation")
                    frappe.throw(_(f"Impossible de créer l'entrepôt cible {target_warehouse_with_company}"))
            except Exception as e:
                print(f"Failed to create target warehouse {target_warehouse_with_company}: {str(e)}", "Warehouse Creation")
                frappe.throw(_(f"Impossible de créer l'entrepôt cible {target_warehouse_with_company}: {str(e)}"))

        # Verify warehouse exists before setting it
        if not frappe.db.exists("Warehouse", target_warehouse_with_company):
            frappe.throw(_(f"Could not find Set Target Warehouse: {target_warehouse_with_company}"))

        # Get ref from data
        ref = data.get("ref")
        if not ref:
            frappe.throw(_("Aucun champ 'ref' spécifié dans les données pour le Material Request."))

        # Check for existing Material Request with the same ref
        if frappe.db.exists("Material Request", {"ref": ref}):
            frappe.throw(_(f"Un Material Request avec le ref {ref} existe déjà. Veuillez utiliser une référence unique."))

        mr = frappe.get_doc({
            "doctype": "Material Request",
            "ref": ref,  # Set the new ref field
            "material_request_type": data["material_request_type"],
            "transaction_date": data["transaction_date"],
            "schedule_date": data.get("schedule_date") or data["transaction_date"],
            "status": data.get("status", "Draft"),
            "set_warehouse": target_warehouse_with_company,
            "company": company,
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
        frappe.msgprint(_(f"Material Request {mr.name} créé avec succès"))
        return mr.name
    except Exception as e:
        frappe.db.rollback()
        print(f"Failed to create Material Request with ref {data.get('ref', 'unknown')}: {str(e)}", "Material Request Creation")
        frappe.throw(_(f"Erreur lors de la création du Material Request: {str(e)}"))
        
@frappe.whitelist()
def create_request_for_quotation_from_mr(mr_ref, supplier_names):
    try:
        # Find Material Request by ref
        mr_name = frappe.db.get_value("Material Request", {"ref": mr_ref}, "name")
        if not mr_name:
            frappe.throw(_(f"Material Request avec ref {mr_ref} n'existe pas"))

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
        frappe.msgprint(_(f"Request for Quotation {rfq.name} créé avec succès"))
        return rfq.name
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_(f"Erreur lors de la création du Request for Quotation: {str(e)}"))
        
@frappe.whitelist()
def process_csv3_data(records):
    try:
        # Log input records for debugging
        print(f"csv3 records: {records}", "Debug csv3 processing")
        result = {}
        for record in records:
            ref = record.get("ref_request_quotation")
            supplier = record.get("supplier")
            
            if not ref:
                frappe.throw(_(f"Aucune valeur 'ref_request_quotation' spécifiée dans la ligne: {record}"))

            # Normalize ref to string and remove whitespace
            ref = str(ref).strip()
            print(f"Processing ref: {ref} (type: {type(ref)})", "Debug csv3 ref")

            # Check if Material Request exists by ref field, considering docstatus
            mr_name = frappe.db.get_value(
                "Material Request",
                {"ref": ref, "docstatus": ["<", 2]},  # Exclude Cancelled
                "name",
                as_dict=False
            )
            if not mr_name:
                # Log all existing Material Requests for debugging
                existing_refs = frappe.db.get_all(
                    "Material Request",
                    fields=["name", "ref", "docstatus"],
                    filters={"docstatus": ["<", 2]}
                )
                print(f"Existing Material Requests: {existing_refs}", "Debug Material Request Lookup")
                frappe.throw(_(f"Material Request avec ref {ref} n'existe pas"))

            if ref not in result:
                result[ref] = []
            if supplier and supplier not in result[ref]:
                result[ref].append(supplier)
        
        return [{"ref_request_quotation": k, "suppliers": v} for k, v in result.items()]
    except Exception as e:
        print(f"csv3 processing error: {str(e)}", "Debug csv3 error")
        frappe.throw(_(f"Erreur lors du traitement des données csv3: {str(e)}"))
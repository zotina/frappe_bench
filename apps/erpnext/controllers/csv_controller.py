from erpnext.services.data2_service import create_item, create_material_request, create_request_for_quotation_from_mr, create_supplier, process_csv3_data
import frappe
import base64
from io import StringIO
from erpnext.services.CsvService import CsvService

@frappe.whitelist(allow_guest=False)
def import_csvs_from_json(data):
    response = {
        "success": False,
        "message": "",
        "validation_errors": [],
        "inserted_records": {}
    }

    try:
        if isinstance(data, str):
            data = frappe.parse_json(data)

        csv_configs = [
            {"file_key": "csv1", "doctype": "csv1"},
            {"file_key": "csv2", "doctype": "csv2"},
            {"file_key": "csv3", "doctype": "csv3"}
        ]

        all_errors = []
        all_parsed_data = {}
        all_inserted_records = {}

        # PHASE 1: Validate all CSVs
        for config in csv_configs:
            file_key = config["file_key"]
            doctype = config["doctype"]
            file_content_b64 = data.get(file_key, "")

            if not file_content_b64:
                all_errors.append({
                    "line": 0,
                    "error_message": f"{file_key} est requis",
                    "data": {},
                    "file": file_key
                })
                continue

            if not frappe.db.exists("DocType", doctype):
                all_errors.append({
                    "line": 0,
                    "error_message": f"Le DocType '{doctype}' n'existe pas",
                    "data": {},
                    "file": file_key
                })
                continue

            try:
                file_content = base64.b64decode(file_content_b64)
            except Exception as e:
                all_errors.append({
                    "line": 0,
                    "error_message": f"Erreur de décodage Base64 pour {file_key}: {str(e)}",
                    "data": {},
                    "file": file_key
                })
                continue

            error_list, parsed_data = CsvService.import_csv(file_content, doctype)
            
            if error_list:
                for error in error_list:
                    error["file"] = file_key
                all_errors.extend(error_list)
            
            if not parsed_data:
                all_errors.append({
                    "line": 0,
                    "error_message": f"Aucune donnée valide trouvée dans {file_key}",
                    "data": {},
                    "file": file_key
                })
                continue

            all_parsed_data[doctype] = parsed_data

        # If validation errors exist, return early
        if all_errors:
            response["message"] = "Des erreurs sont survenues lors de la validation des fichiers CSV"
            response["validation_errors"] = all_errors
            return response

        # PHASE 2: Process all CSVs in a single transaction
        frappe.db.begin()
        try:
            for config in csv_configs:
                doctype = config["doctype"]
                file_key = config["file_key"]
                if doctype not in all_parsed_data:
                    continue

                parsed_data = all_parsed_data[doctype]
                csv_errors = []
                csv_inserted_records = []

                if doctype == "csv1":
                    for idx, record in enumerate(parsed_data, start=1):
                        try:
                            # Simulate Item creation
                            item_data = {
                                "item_code": f"{record.get('item_name')}-{frappe.generate_hash(length=4)}",
                                "item_name": record.get("item_name"),
                                "item_group": record.get("item_groupe")
                            }
                            item_name = create_item(item_data)

                            # Simulate Material Request creation
                            mr_data = {
                                "material_request_type": record.get("purpose"),
                                "transaction_date": record.get("date"),
                                "schedule_date": record.get("required_by"),
                                "status": "Submitted",
                                "target_warehouse": record.get("target_warehouse"),
                                "ref": record.get("ref"),
                                "items": [{
                                    "item_code": item_name,
                                    "qty": float(record.get("quantity"))
                                }]
                            }
                            mr_name = create_material_request(mr_data)

                            csv_inserted_records.append({"item": item_name, "material_request": mr_name})
                        except Exception as e:
                            csv_errors.append({
                                "line": idx,
                                "error_message": f"Erreur d'insertion csv1: {str(e)}",
                                "data": record,
                                "file": file_key
                            })
                            continue  # Continue to the next record

                elif doctype == "csv2":
                    for idx, record in enumerate(parsed_data, start=1):
                        try:
                            supplier_data = {
                                "supplier_name": record.get("supplier_name"),
                                "country": record.get("country"),
                                "type": record.get("type") or record.get("_type")
                            }
                            supplier_name = create_supplier(supplier_data)
                            csv_inserted_records.append({"supplier": supplier_name})
                        except Exception as e:
                            csv_errors.append({
                                "line": idx,
                                "error_message": f"Erreur d'insertion csv2: {str(e)}",
                                "data": record,
                                "file": file_key
                            })
                            continue  # Continue to the next record

                elif doctype == "csv3":
                    try:
                        processed_data = process_csv3_data(parsed_data)
                        for idx, record in enumerate(processed_data, start=1):
                            try:
                                rfq_name = create_request_for_quotation_from_mr(
                                    record["ref_request_quotation"],
                                    record["suppliers"]
                                )
                                csv_inserted_records.append({"request_for_quotation": rfq_name})
                            except Exception as e:
                                csv_errors.append({
                                    "line": idx,
                                    "error_message": f"Erreur d'insertion csv3: {str(e)}",
                                    "data": record,
                                    "file": file_key
                                })
                                continue  # Continue to the next record
                    except Exception as e:
                        csv_errors.append({
                            "line": 0,
                            "error_message": f"Erreur de traitement csv3: {str(e)}",
                            "data": {},
                            "file": file_key
                        })

                # If errors occurred in this CSV, store them
                if csv_errors:
                    all_errors.extend(csv_errors)

                # Store inserted records even if errors, to report partial success
                if csv_inserted_records:
                    all_inserted_records[file_key] = csv_inserted_records

            # PHASE 3: Commit or rollback based on errors
            if all_errors:
                frappe.db.rollback()
                response["success"] = False
                response["message"] = "Certaines insertions ont échoué. Toutes les modifications ont été annulées."
                response["validation_errors"] = all_errors
                response["inserted_records"] = all_inserted_records
            else:
                frappe.db.commit()
                response["success"] = True
                response["message"] = "Tous les CSV ont été importés avec succès."
                response["inserted_records"] = all_inserted_records

        except Exception as e:
            frappe.db.rollback()
            response["success"] = False
            response["message"] = f"Erreur inattendue lors de l'insertion: {str(e)}"
            response["validation_errors"] = [{
                "line": 0,
                "error_message": f"Erreur inattendue: {str(e)}",
                "data": {},
                "file": "global"
            }]
            response["inserted_records"] = all_inserted_records

        return response

    except Exception as e:
        frappe.db.rollback()
        response["message"] = f"Erreur inattendue: {str(e)}"
        response["validation_errors"] = [{
            "line": 0,
            "error_message": f"Erreur inattendue: {str(e)}",
            "data": {},
            "file": "global"
        }]
        return response
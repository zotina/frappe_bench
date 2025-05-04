import frappe
import base64
from io import StringIO
from erpnext.services.CsvService import CsvService

@frappe.whitelist(allow_guest=False)
def import_csv_from_json(data):
    response = {
        "success": False,
        "message": "",
        "validation_errors": [],
        "inserted_records": []
    }

    print("Début de import_csv_from_json")

    try:
        if isinstance(data, str):
            data = frappe.parse_json(data)
            print("Données JSON parsées")

        file_content_b64 = data.get("filecontent", "")
        doctype = "Teste"

        if not file_content_b64:
            response["message"] = "filecontent est requis"
            response["validation_errors"].append({
                "line": 0,
                "error_message": "filecontent est requis",
                "data": {}
            })
            print("Erreur: filecontent est requis")
            return response

        if not frappe.db.exists("DocType", doctype):
            response["message"] = f"Le DocType '{doctype}' n'existe pas"
            response["validation_errors"].append({
                "line": 0,
                "error_message": f"Le DocType '{doctype}' n'existe pas",
                "data": {}
            })
            print(f"Erreur: Le DocType '{doctype}' n'existe pas")
            return response

        try:
            file_content = base64.b64decode(file_content_b64)
            print("Fichier décodé avec succès")
        except Exception as e:
            response["message"] = "Le format du fichier est invalide"
            response["validation_errors"].append({
                "line": 0,
                "error_message": f"Erreur de décodage Base64: {str(e)}",
                "data": {}
            })
            print(f"Erreur de décodage Base64: {str(e)}")
            return response

        error_list, parsed_data = CsvService.import_csv(file_content, doctype)
        print(f"Données parsées: {len(parsed_data)} enregistrements")

        if error_list:
            response["message"] = "Validation errors occurred during CSV parsing or validation"
            response["validation_errors"] = error_list
            print(f"Validation errors found: {len(error_list)} errors")
            return response

        if not parsed_data:
            response["success"] = True
            response["message"] = "No valid data to insert"
            response["inserted_records"] = []
            print("Aucune donnée valide à insérer")
            return response

        inserted_records = []
        for record in parsed_data:
            try:
                doc = frappe.get_doc({
                    "doctype": doctype,
                    **record
                })
                doc.insert()
                inserted_records.append(doc.name)
                print(f"Enregistrement inséré: {doc.name}")
            except Exception as e:
                error_list.append({
                    "line": 0,
                    "error_message": f"Insertion error: {str(e)}",
                    "data": record
                })
                print(f"Erreur d'insertion pour l'enregistrement {record}: {str(e)}")

        if error_list:
            response["message"] = "Errors occurred during insertion"
            response["validation_errors"] = error_list
        else:
            response["success"] = True
            response["message"] = f"{len(inserted_records)} records inserted successfully"
            response["inserted_records"] = inserted_records
            frappe.db.commit()
            print(f"{len(inserted_records)} enregistrements insérés avec succès")

        return response

    except Exception as e:
        print(f"Erreur globale dans import_csv_from_json: {str(e)}")
        response["message"] = f"Erreur inattendue: {str(e)}"
        return response
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint, format_date
from erpnext.controllers.api.utils import validate_jwt

@frappe.whitelist(allow_guest=False)
@validate_jwt
def get_teste_list():
    """
    Returns a JSON list of all records from the 'Teste' doctype
    
    Example usage:
    http://erpnext.localhost:8000/api/method/erpnext.controllers.api.page.test_api_controller.get_teste_list
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        # Get parameters for pagination if provided
        limit = cint(frappe.local.form_dict.get('limit', 20))
        offset = cint(frappe.local.form_dict.get('offset', 0))
        
        # Query the database for Teste records with specific fields
        teste_records = frappe.get_all(
            "Teste",
            fields=["name", "libelle", "date_naissance", "creation", "modified"],
            limit=limit,
            start=offset,
            order_by="creation desc"
        )
        
        # Format dates for better readability
        for record in teste_records:
            if record.get("date_naissance"):
                record["date_naissance_formatted"] = format_date(record["date_naissance"])
        
        # Return the records as JSON
        return teste_records
        
    except Exception as e:
        print(f"Error in Test_controller_api.get_teste_list: {str(e)}")
        return {"error": str(e)}

@frappe.whitelist(allow_guest=False)
@validate_jwt
def get_teste_details(name):
    """
    Returns detailed information for a specific Teste record
    
    Example usage:
    /api/method/erpnext.controllers.api.page.test_api_controller.get_teste_details?name=TESTE00001
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        if not name:
            frappe.throw(_("Name parameter is required"))
            
        # Fetch the complete document
        doc = frappe.get_doc("Teste", name)
        
        # Convert to dictionary
        result = doc.as_dict()
        
        # Format date for better readability
        if result.get("date_naissance"):
            result["date_naissance_formatted"] = format_date(result["date_naissance"])
        
        # Return as dict (will be converted to JSON)
        return result
        
    except Exception as e:
        print(f"Error in Test_controller_api.get_teste_details: {str(e)}")
        return {"error": str(e)}

@frappe.whitelist(allow_guest=False)
@validate_jwt
def search_teste(query=""):
    """
    Search for Teste records matching the query string in libelle field
    
    Example usage:
    /api/method/erpnext.controllers.api.page.test_api_controller.search_teste?query=example
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        if not query:
            return []
            
        # Search in libelle field
        results = frappe.db.sql("""
            SELECT name, libelle, date_naissance, creation, modified
            FROM `tabTeste`
            WHERE `libelle` LIKE %s
            ORDER BY creation DESC
            LIMIT 20
        """, [f"%{query}%"], as_dict=True)
        
        # Format dates for better readability
        for record in results:
            if record.get("date_naissance"):
                record["date_naissance_formatted"] = format_date(record["date_naissance"])
        
        return results
        
    except Exception as e:
        print(f"Error in Test_controller_api.search_teste: {str(e)}")
        return {"error": str(e)}

@frappe.whitelist(allow_guest=False)
@validate_jwt
def filter_by_date(start_date=None, end_date=None):
    """
    Filter Teste records by date_naissance range
    
    Example usage:
    /api/method/erpnext.controllers.api.page.test_api_controller.filter_by_date?start_date=2000-01-01&end_date=2010-12-31
    Header: Authorization: Bearer <jwt_token>
    """
    try:
        filters = {}
        
        if start_date:
            filters["date_naissance"] = [">=", start_date]
        
        if end_date:
            if "date_naissance" in filters:
                filters["date_naissance"] = ["between", [start_date, end_date]]
            else:
                filters["date_naissance"] = ["<=", end_date]
        
        results = frappe.get_all(
            "Teste",
            fields=["name", "libelle", "date_naissance", "creation", "modified"],
            filters=filters,
            limit=50,
            order_by="date_naissance asc"
        )
        
        # Format dates for better readability
        for record in results:
            if record.get("date_naissance"):
                record["date_naissance_formatted"] = format_date(record["date_naissance"])
        
        return results
        
    except Exception as e:
        print(f"Error in Test_controller_api.filter_by_date: {str(e)}")
        return {"error": str(e)}
import frappe
from erpnext.controllers.api.utils import validate_jwt

@frappe.whitelist()
@validate_jwt
def get_sample_data():
    return {"message": "This is a secure API response", "user": frappe.session.user}
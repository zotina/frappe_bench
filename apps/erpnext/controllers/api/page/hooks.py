from frappe import whitelist
from erpnext.controllers.api.utils import validate_jwt
import functools

def patch_whitelisted_methods():
    frappe.log_error("patch_whitelisted_methods: Début du patch")
    for method in frappe.get_all("Whitelisted Method"):
        frappe.log_error(f"Method: {method.method}, Module: {frappe.get_attr(method.method).__module__}")
        method = frappe.get_attr(method.method)
        if method.__module__.startswith("erpnext.controllers.api.page"):
            frappe.log_error(f"Applying validate_jwt to {method.__name__}")
            setattr(method, "__wrapped__", validate_jwt(method))
            frappe.whitelist(method.__wrapped__)

boot_session = patch_whitelisted_methods
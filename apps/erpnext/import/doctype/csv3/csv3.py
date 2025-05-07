import frappe
from frappe import _
from frappe.model.document import Document

class csv3(Document):
    # begin: auto-generated types
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        ref_request_quotation: DF.LongText | None
        supplier: DF.LongText | None
    # end: auto-generated types

    @staticmethod
    def validate_ref_request_quotation(data):
        if not data:
            frappe.throw(_("Le champ 'ref_request_quotation' est obligatoire"))

    @staticmethod
    def validate_supplier(data):
        if not data:
            frappe.throw(_("Le champ 'supplier' est obligatoire"))

    def validateAll(self, fieldName, data):
        """Validate the data for the given fieldName by calling the appropriate validation method."""
        validators = {
            "ref_request_quotation": self.__class__.validate_ref_request_quotation,
            "supplier": self.__class__.validate_supplier
        }
        validator = validators.get(fieldName)
        if validator:
            validator(data)
        else:
            frappe.throw(_(f"Aucune méthode de validation n'existe pour le champ '{fieldName}'"))
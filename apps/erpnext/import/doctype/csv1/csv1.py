import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

class csv1(Document):
    # begin: auto-generated types
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        date: DF.Date | None
        item_groupe: DF.LongText | None
        item_name: DF.LongText | None
        purpose: DF.LongText | None
        quantity: DF.LongText | None
        ref: DF.LongText | None
        required_by: DF.Date | None
        target_warehouse: DF.LongText | None
    # end: auto-generated types

    @staticmethod
    def validate_date(data):
        if not data:
            frappe.throw(_("Le champ 'date' est obligatoire"))
        try:
            getdate(data)  # Validate date format
        except ValueError:
            frappe.throw(_("Le champ 'date' doit être une date valide"))

    @staticmethod
    def validate_item_name(data):
        if not data:
            frappe.throw(_("Le champ 'item_name' est obligatoire"))

    @staticmethod
    def validate_item_groupe(data):
        if not data:
            frappe.throw(_("Le champ 'item_groupe' est obligatoire"))
        if not frappe.db.exists("Item Group", data):
            frappe.throw(_("L'item_groupe '{0}' n'existe pas dans Item Group").format(data))

    @staticmethod
    def validate_required_by(data):
        if not data:
            frappe.throw(_("Le champ 'required_by' est obligatoire"))
        try:
            getdate(data)  # Validate date format
        except ValueError:
            frappe.throw(_("Le champ 'required_by' doit être une date valide"))

    @staticmethod
    def validate_quantity(data):
        if not data:
            frappe.throw(_("Le champ 'quantity' est obligatoire"))
        try:
            qty = float(data)
            if qty <= 0:
                frappe.throw(_("La quantité doit être supérieure à 0"))
        except ValueError:
            frappe.throw(_("La quantité doit être un nombre valide"))

    @staticmethod
    def validate_purpose(data):
        if not data:
            frappe.throw(_("Le champ 'purpose' est obligatoire"))

    @staticmethod
    def validate_target_warehouse(data):
        if not data:
            frappe.throw(_("Le champ 'target_warehouse' est obligatoire"))

    @staticmethod
    def validate_ref(data):
        if not data:
            frappe.throw(_("Le champ 'ref' est obligatoire"))
        if frappe.db.exists("Material Request", {"ref": data}):
            frappe.throw(_("Un Material Request avec le ref '{0}' existe déjà").format(data))

    def validateAll(self, fieldName, data):
        """Validate the data for the given fieldName by calling the appropriate validation method."""
        validators = {
            "date": self.__class__.validate_date,
            "item_name": self.__class__.validate_item_name,
            "item_groupe": self.__class__.validate_item_groupe,
            "required_by": self.__class__.validate_required_by,
            "quantity": self.__class__.validate_quantity,
            "purpose": self.__class__.validate_purpose,
            "target_warehouse": self.__class__.validate_target_warehouse,
            "ref": self.__class__.validate_ref
        }
        validator = validators.get(fieldName)
        if validator:
            validator(data)
        else:
            frappe.throw(_(f"Aucune méthode de validation n'existe pour le champ '{fieldName}'"))
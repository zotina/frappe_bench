import frappe
from frappe import _
from frappe.model.document import Document
from erpnext.utilities.country_normalizer import CountryNormalizer

class csv2(Document):
    # begin: auto-generated types
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        country: DF.LongText | None
        supplier_name: DF.LongText | None
        type: DF.LongText | None
    # end: auto-generated types

    @staticmethod
    def validate_supplier_name(data):
        if not data:
            frappe.throw(_("Le champ 'supplier_name' est obligatoire"))

    @staticmethod
    def validate_country(data):
        if not data:
            frappe.throw(_("Le champ 'country' est obligatoire"))
        # Normalize country name
        country = CountryNormalizer.normalize_country(data)
        if not frappe.db.exists("Country", country):
            frappe.throw(_("Le pays '{0}' n'existe pas dans Country").format(country))

    @staticmethod
    def validate_type(data):
        if not data:
            frappe.throw(_("Le champ 'type' est obligatoire"))
        if data not in ["Company", "Individual"]:
            frappe.throw(_("Le type de fournisseur doit être 'Company' ou 'Individual'"))

    def validateAll(self, fieldName, data):
        """Validate the data for the given fieldName by calling the appropriate validation method."""
        validators = {
            "supplier_name": self.__class__.validate_supplier_name,
            "country": self.__class__.validate_country,
            "type": self.__class__.validate_type
        }
        validator = validators.get(fieldName)
        if validator:
            validator(data)
        else:
            frappe.throw(_(f"Aucune méthode de validation n'existe pour le champ '{fieldName}'"))
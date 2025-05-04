import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate
from datetime import datetime
import re

class Teste(Document):
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from frappe.types import DF
        date_naissance: DF.Date | None
        libelle: DF.LongText | None

    @staticmethod
    def validate_libelle(data):
        if not data:
            frappe.throw(_("Le champ 'libelle' est obligatoire"))

    @staticmethod
    def validate_date_naissance(data):
        if not data:
            frappe.throw(_("La date de naissance est obligatoire"))
        date = getdate(data)
        today = getdate()
        if date > today:
            frappe.throw(_("La date de naissance ne peut pas être dans le futur"))
        current_year = today.year
        birth_year = date.year
        age = current_year - birth_year
        if today.month < date.month or (today.month == date.month and today.day < date.day):
            age -= 1
        if age < 18:
            frappe.throw(_("La personne doit avoir au moins 18 ans"))

    def validateAll(self, fieldName, data):
        """Validate the data for the given fieldName by calling the appropriate validation method."""
        if fieldName == "libelle":
            self.__class__.validate_libelle(data)
        elif fieldName == "date_naissance":
            self.__class__.validate_date_naissance(data)
        else:
            frappe.throw(_(f"No validation method exists for field '{fieldName}'"))
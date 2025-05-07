import frappe
from frappe import _

@frappe.whitelist()
def reset_tables():
    try:
        table_names = [
            "Stock Entry Detail",
            "Stock Ledger Entry",
            "Stock Entry",
            "Material Request Item", 
            "Request for Quotation Item",
            "Supplier Quotation Item",
            "Purchase Order Item",
            "Purchase Receipt Item",
            "Purchase Invoice Item",
            "Payment Entry Reference",
            "Material Request", 
            "Request for Quotation",
            "Supplier Quotation",
            "Purchase Order",
            "Purchase Receipt",
            "Purchase Invoice",
            "Payment Entry",
            "Payment Request",
            "Payment Ledger Entry",
            "GL Entry",
            "Bin",
            "Item",
            "Supplier",
            "Warehouse"
        ]

        for table in table_names:
            frappe.db.delete(table)
            frappe.db.commit()

            frappe.log_error(
                message=f"Données de la table {table} réinitialisées par {frappe.session.user}",
                title="Réinitialisation de table"
            )

        frappe.msgprint(_("Les données des tables {0} ont été réinitialisées avec succès.").format(", ".join(table_names)))
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(
            message=f"Erreur lors de la réinitialisation: {str(e)}",
            title="Erreur de réinitialisation"
        )
        frappe.msgprint(_("Erreur lors de la réinitialisation des tables: {0}").format(str(e)))
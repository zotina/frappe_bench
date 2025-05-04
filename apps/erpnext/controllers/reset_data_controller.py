import frappe
from frappe import _

@frappe.whitelist()
def reset_tables():
    try:
        table_names = ["Teste"]

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
        frappe.msgprint("Erreur lors de la réinitialisation des tables")
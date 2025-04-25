frappe.pages['resetpage'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Reset Data',
        single_column: true
    });

    page.set_primary_action(__('Reset'), function() {
        frappe.confirm(
            __('Êtes-vous sûr de vouloir réinitialiser les données des tables ? Cette action est irréversible.'),
            function() {
                
                frappe.call({
                    method: 'erpnext.controllers.reset_data_controller.reset_tables',
                    callback: function(response) {
                        if (response.message) {
                            frappe.msgprint(response.message);
                        }
                    },
                    error: function(err) {
                        frappe.msgprint(__('Erreur lors de l\'appel de la fonction de réinitialisation.'));
                        console.error(err);
                    }
                });
            },
            function() {
                frappe.msgprint(__('Opération annulée.'));
            }
        );
    });
};
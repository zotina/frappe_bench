frappe.pages['importpage'].on_page_load = function(wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Importation de fichiers CSV',
        single_column: true
    });

    $(wrapper).find('.page-content').html(`
        <div class="import-data-container" style="display: flex; justify-content: center; align-items: center; min-height: 100%;">
            <div class="import-data-box" style="background: #fff; border: 1px solid #d1d8dd; border-radius: 8px; padding: 20px; width: 600px; max-width: 90%; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px auto;">
                <h3 style="text-align: center; margin-bottom: 20px;">Importer des Données</h3>
                <form id="import-data-form">
                    <div class="form-group" style="margin-bottom: 15px;">
                        <label for="file-upload" style="display: block; margin-bottom: 5px;">Sélectionner un fichier (CSV) :</label>
                        <input type="file" id="file-upload" name="file" accept=".csv" class="form-control" style="width: 100%;" required>
                    </div>
                    <button type="submit" class="btn btn-primary btn-import" style="width: 100%; padding: 10px;">Importer</button>
                </form>
                <div id="import-status" style="margin-top: 15px; text-align: center;"></div>
                <div id="import-errors" style="margin-top: 15px;"></div>
            </div>
        </div>
    `);

    $('#import-data-form').on('submit', async function(e) {
        e.preventDefault();
        const fileInput = document.getElementById('file-upload');
        if (!fileInput.files.length) {
            frappe.msgprint(__('Veuillez sélectionner un fichier CSV.'));
            return;
        }
        const file = fileInput.files[0];
        const doctype = "Teste";
        
        $('#import-status').html('<div class="alert alert-info">Importation en cours...</div>');
        $('#import-errors').html(''); 
        
        const fileContent = await readFileAsBase64(file);
        frappe.call({
            method: 'erpnext.controllers.csv_controller.import_csv_from_json',
            args: {
                data: {
                    filecontent: fileContent,
                    doctype: doctype
                }
            },
            callback: function(response) {
                const result = response.message;
                
                if (result.success) {
                    const recordCount = result.inserted_records ? result.inserted_records.length : 0;
                    $('#import-status').html(`<div class="alert alert-success">Importation terminée avec succès ! ${recordCount} enregistrements importés.</div>`);
                } else {
                    $('#import-status').html(`<div class="alert alert-danger">${frappe.utils.escape_html(result.message)}</div>`);
                    
                    if (result.validation_errors && result.validation_errors.length > 0) {
                        let errorMessage = '<div class="alert alert-danger"><h3>Erreurs de validation</h3><ul>';
                        result.validation_errors.forEach(function(error) {
                            errorMessage += `
                                <li>
                                    <strong>Ligne ${error.line}:</strong> ${frappe.utils.escape_html(error.error_message)}<br>
                                </li>
                            `;
                        });
                        errorMessage += '</ul></div>';
                        $('#import-errors').html(errorMessage);
                    } else {
                        $('#import-errors').html(`<div class="alert alert-danger">${frappe.utils.escape_html(result.message)}</div>`);
                    }
                }
            }
        });

        function readFileAsBase64(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = e => resolve(e.target.result.split(',')[1]);
                reader.onerror = e => reject(e);
                reader.readAsDataURL(file);
            });
        }
    });
};
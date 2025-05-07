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
                        <label for="csv1-upload" style="display: block; margin-bottom: 5px;">Fichier CSV 1 (Items et Material Requests) :</label>
                        <input type="file" id="csv1-upload" name="csv1" accept=".csv" class="form-control" style="width: 100%;">
                    </div>
                    <div class="form-group" style="margin-bottom: 15px;">
                        <label for="csv2-upload" style="display: block; margin-bottom: 5px;">Fichier CSV 2 (Suppliers) :</label>
                        <input type="file" id="csv2-upload" name="csv2" accept=".csv" class="form-control" style="width: 100%;">
                    </div>
                    <div class="form-group" style="margin-bottom: 15px;">
                        <label for="csv3-upload" style="display: block; margin-bottom: 5px;">Fichier CSV 3 (Request for Quotations) :</label>
                        <input type="file" id="csv3-upload" name="csv3" accept=".csv" class="form-control" style="width: 100%;">
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

        const fileInputs = {
            'csv1': document.getElementById('csv1-upload'),
            'csv2': document.getElementById('csv2-upload'),
            'csv3': document.getElementById('csv3-upload')
        };

        // Check if at least one file is selected
        let hasFile = false;
        for (const key in fileInputs) {
            if (fileInputs[key].files.length > 0) {
                hasFile = true;
                break;
            }
        }

        if (!hasFile) {
            frappe.msgprint(__('Veuillez sélectionner au moins un fichier CSV.'));
            return;
        }

        $('#import-status').html('<div class="alert alert-info">Importation en cours...</div>');
        $('#import-errors').html('');

        const data = {};

        // Read all selected files
        for (const key in fileInputs) {
            const fileInput = fileInputs[key];
            if (fileInput.files.length > 0) {
                try {
                    const fileContent = await readFileAsBase64(fileInput.files[0]);
                    data[key] = fileContent;
                } catch (error) {
                    $('#import-status').html(`<div class="alert alert-danger">Erreur lors de la lecture du fichier ${key}</div>`);
                    return;
                }
            }
        }

        frappe.call({
            method: 'erpnext.controllers.csv_controller.import_csvs_from_json',
            args: {
                data: data
            },
            callback: function(response) {
                const result = response.message;

                if (result.success) {
                    let recordCount = 0;
                    for (const doctype in result.inserted_records) {
                        recordCount += result.inserted_records[doctype].length;
                    }
                    $('#import-status').html(`<div class="alert alert-success">Importation terminée avec succès ! ${recordCount} enregistrements importés.</div>`);
                    
                    // Display inserted records by doctype
                    let recordsMessage = '<div class="alert alert-success"><h4>Enregistrements importés</h4><ul>';
                    for (const doctype in result.inserted_records) {
                        recordsMessage += `<li><strong>${doctype}:</strong> ${result.inserted_records[doctype].length} enregistrements</li>`;
                    }
                    recordsMessage += '</ul></div>';
                    $('#import-errors').html(recordsMessage);
                } else {
                    $('#import-status').html(`<div class="alert alert-danger">${frappe.utils.escape_html(result.message)}</div>`);

                    if (result.validation_errors && result.validation_errors.length > 0) {
                        let errorMessage = '<div class="alert alert-danger"><h3>Erreurs de validation</h3><ul>';
                        result.validation_errors.forEach(function(error) {
                            errorMessage += `
                                <li>
                                    <strong>Ligne ${error.line}:</strong> ${frappe.utils.escape_html(error.error_message)}<br>
                                    <small>Données: ${frappe.utils.escape_html(JSON.stringify(error.data))}</small>
                                </li>
                            `;
                        });
                        errorMessage += '</ul></div>';
                        $('#import-errors').html(errorMessage);
                    } else {
                        $('#import-errors').html(`<div class="alert alert-danger">${frappe.utils.escape_html(result.message)}</div>`);
                    }
                }
            },
            error: function(xhr, status, error) {
                $('#import-status').html(`<div class="alert alert-danger">Erreur serveur: ${frappe.utils.escape_html(error)}</div>`);
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
(() => {
  // ../erpnext/erpnext/public/js/bank_reconciliation_tool/data_table_manager.js
  frappe.provide("erpnext.accounts.bank_reconciliation");
  erpnext.accounts.bank_reconciliation.DataTableManager = class DataTableManager {
    constructor(opts) {
      Object.assign(this, opts);
      this.dialog_manager = new erpnext.accounts.bank_reconciliation.DialogManager(
        this.company,
        this.bank_account,
        this.bank_statement_from_date,
        this.bank_statement_to_date,
        this.filter_by_reference_date,
        this.from_reference_date,
        this.to_reference_date
      );
      this.make_dt();
    }
    make_dt() {
      const me = this;
      frappe.call({
        method: "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.get_bank_transactions",
        args: {
          bank_account: this.bank_account,
          from_date: this.bank_statement_from_date,
          to_date: this.bank_statement_to_date
        },
        callback: function(response) {
          me.format_data(response.message);
          me.get_dt_columns();
          me.get_datatable();
          me.set_listeners();
        }
      });
    }
    get_dt_columns() {
      this.columns = [
        {
          name: __("Date"),
          editable: false,
          width: 100,
          format: frappe.form.formatters.Date
        },
        {
          name: __("Party Type"),
          editable: false,
          width: 95
        },
        {
          name: __("Party"),
          editable: false,
          width: 100
        },
        {
          name: __("Description"),
          editable: false,
          width: 350
        },
        {
          name: __("Deposit"),
          editable: false,
          width: 100,
          format: (value) => "<span style='color:green;'>" + format_currency(value, this.currency) + "</span>"
        },
        {
          name: __("Withdrawal"),
          editable: false,
          width: 100,
          format: (value) => "<span style='color:red;'>" + format_currency(value, this.currency) + "</span>"
        },
        {
          name: __("Unallocated Amount"),
          editable: false,
          width: 100,
          format: (value) => "<span style='color:var(--blue-500);'>" + format_currency(value, this.currency) + "</span>"
        },
        {
          name: __("Reference Number"),
          editable: false,
          width: 140
        },
        {
          name: __("Actions"),
          editable: false,
          sortable: false,
          focusable: false,
          dropdown: false,
          width: 100
        }
      ];
    }
    format_data(transactions) {
      this.transactions = [];
      if (transactions[0]) {
        this.currency = transactions[0]["currency"];
      }
      this.transaction_dt_map = {};
      let length;
      transactions.forEach((row) => {
        length = this.transactions.push(this.format_row(row));
        this.transaction_dt_map[row["name"]] = length - 1;
      });
    }
    format_row(row) {
      return [
        row["date"],
        row["party_type"],
        frappe.form.formatters.Link(row["party"], { options: row["party_type"] }),
        row["description"],
        row["deposit"],
        row["withdrawal"],
        row["unallocated_amount"],
        row["reference_number"],
        `<button class="btn btn-primary btn-xs center" data-name="${row["name"]}">${__(
          "Actions"
        )}</button>`
      ];
    }
    get_datatable() {
      const datatable_options = {
        columns: this.columns,
        data: this.transactions,
        dynamicRowHeight: true,
        checkboxColumn: false,
        inlineFilters: true
      };
      this.datatable = new frappe.DataTable(this.$reconciliation_tool_dt.get(0), datatable_options);
      $(`.${this.datatable.style.scopeClass} .dt-scrollable`).css("max-height", "calc(100vh - 400px)");
      if (this.transactions.length > 0) {
        this.$reconciliation_tool_dt.show();
        this.$no_bank_transactions.hide();
      } else {
        this.$reconciliation_tool_dt.hide();
        this.$no_bank_transactions.show();
      }
    }
    set_listeners() {
      var me = this;
      $(`.${this.datatable.style.scopeClass} .dt-scrollable`).on("click", `.btn`, function() {
        me.dialog_manager.show_dialog(
          $(this).attr("data-name"),
          (bank_transaction) => me.update_dt_cards(bank_transaction)
        );
        return true;
      });
    }
    update_dt_cards(bank_transaction) {
      const transaction_index = this.transaction_dt_map[bank_transaction.name];
      if (bank_transaction.unallocated_amount > 0) {
        this.transactions[transaction_index] = this.format_row(bank_transaction);
      } else {
        this.transactions.splice(transaction_index, 1);
        for (const [k, v] of Object.entries(this.transaction_dt_map)) {
          if (v > transaction_index)
            this.transaction_dt_map[k] = v - 1;
        }
      }
      this.datatable.refresh(this.transactions, this.columns);
      if (this.transactions.length == 0) {
        this.$reconciliation_tool_dt.hide();
        this.$no_bank_transactions.show();
      }
      this.get_cleared_balance().then(() => {
        this.cards_manager.$cards[1].set_value(format_currency(this.cleared_balance), this.currency);
        this.cards_manager.$cards[2].set_value(
          format_currency(this.bank_statement_closing_balance - this.cleared_balance),
          this.currency
        );
        this.cards_manager.$cards[2].set_value_color(
          this.bank_statement_closing_balance - this.cleared_balance == 0 ? "text-success" : "text-danger"
        );
      });
    }
    get_cleared_balance() {
      if (this.bank_account && this.bank_statement_to_date) {
        return frappe.call({
          method: "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.get_account_balance",
          args: {
            bank_account: this.bank_account,
            till_date: this.bank_statement_to_date,
            company: this.company
          },
          callback: (response) => this.cleared_balance = response.message
        });
      }
    }
  };

  // ../erpnext/erpnext/public/js/bank_reconciliation_tool/number_card.js
  frappe.provide("erpnext.accounts.bank_reconciliation");
  erpnext.accounts.bank_reconciliation.NumberCardManager = class NumberCardManager {
    constructor(opts) {
      Object.assign(this, opts);
      this.make_cards();
    }
    make_cards() {
      this.$reconciliation_tool_cards.empty();
      this.$cards = [];
      this.$summary = $(`<div class="report-summary"></div>`).hide().appendTo(this.$reconciliation_tool_cards);
      var chart_data = [
        {
          value: this.bank_statement_closing_balance,
          label: __("Closing Balance as per Bank Statement"),
          datatype: "Currency",
          currency: this.currency
        },
        {
          value: this.cleared_balance,
          label: __("Closing Balance as per ERP"),
          datatype: "Currency",
          currency: this.currency
        },
        {
          value: this.bank_statement_closing_balance - this.cleared_balance,
          label: __("Difference"),
          datatype: "Currency",
          currency: this.currency
        }
      ];
      chart_data.forEach((summary) => {
        let number_card = new erpnext.accounts.NumberCard(summary);
        this.$cards.push(number_card);
        number_card.$card.appendTo(this.$summary);
      });
      this.$cards[2].set_value_color(
        this.bank_statement_closing_balance - this.cleared_balance == 0 ? "text-success" : "text-danger"
      );
      this.$summary.css({ "border-bottom": "0px", "margin-left": "0px", "margin-right": "0px" });
      this.$summary.show();
    }
  };
  erpnext.accounts.NumberCard = class NumberCard {
    constructor(options) {
      this.$card = frappe.utils.build_summary_item(options);
    }
    set_value(value) {
      this.$card.find("div").text(value);
    }
    set_value_color(color) {
      this.$card.find("div").removeClass("text-danger text-success").addClass(`${color}`);
    }
    set_indicator(color) {
      this.$card.find("span").removeClass("indicator red green").addClass(`indicator ${color}`);
    }
  };

  // ../erpnext/erpnext/public/js/bank_reconciliation_tool/dialog_manager.js
  frappe.provide("erpnext.accounts.bank_reconciliation");
  erpnext.accounts.bank_reconciliation.DialogManager = class DialogManager {
    constructor(company, bank_account, bank_statement_from_date, bank_statement_to_date, filter_by_reference_date, from_reference_date, to_reference_date) {
      this.bank_account = bank_account;
      this.company = company;
      this.make_dialog();
      this.bank_statement_from_date = bank_statement_from_date;
      this.bank_statement_to_date = bank_statement_to_date;
      this.filter_by_reference_date = filter_by_reference_date;
      this.from_reference_date = from_reference_date;
      this.to_reference_date = to_reference_date;
    }
    show_dialog(bank_transaction_name, update_dt_cards) {
      this.bank_transaction_name = bank_transaction_name;
      this.update_dt_cards = update_dt_cards;
      frappe.call({
        method: "frappe.client.get_value",
        args: {
          doctype: "Bank Transaction",
          filters: { name: this.bank_transaction_name },
          fieldname: [
            "date",
            "deposit",
            "withdrawal",
            "currency",
            "description",
            "name",
            "bank_account",
            "company",
            "reference_number",
            "party_type",
            "party",
            "unallocated_amount",
            "allocated_amount",
            "transaction_type"
          ]
        },
        callback: (r) => {
          if (r.message) {
            this.bank_transaction = r.message;
            r.message.payment_entry = 1;
            r.message.journal_entry = 1;
            this.dialog.set_values(r.message);
            this.copy_data_to_voucher();
            this.dialog.show();
          }
        }
      });
    }
    copy_data_to_voucher() {
      let copied = {
        reference_number: this.bank_transaction.reference_number || this.bank_transaction.description,
        posting_date: this.bank_transaction.date,
        reference_date: this.bank_transaction.date,
        mode_of_payment: this.bank_transaction.transaction_type
      };
      this.dialog.set_values(copied);
    }
    get_linked_vouchers(document_types) {
      frappe.call({
        method: "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.get_linked_payments",
        args: {
          bank_transaction_name: this.bank_transaction_name,
          document_types,
          from_date: this.bank_statement_from_date,
          to_date: this.bank_statement_to_date,
          filter_by_reference_date: this.filter_by_reference_date,
          from_reference_date: this.from_reference_date,
          to_reference_date: this.to_reference_date
        },
        callback: (result) => {
          const data = result.message;
          if (data && data.length > 0) {
            const proposals_wrapper = this.dialog.fields_dict.payment_proposals.$wrapper;
            proposals_wrapper.show();
            this.dialog.fields_dict.no_matching_vouchers.$wrapper.hide();
            this.data = data.map((row) => this.format_row(row));
            this.get_dt_columns();
            this.get_datatable(proposals_wrapper);
          } else {
            const proposals_wrapper = this.dialog.fields_dict.payment_proposals.$wrapper;
            proposals_wrapper.hide();
            this.dialog.fields_dict.no_matching_vouchers.$wrapper.show();
          }
          this.dialog.show();
        }
      });
    }
    get_dt_columns() {
      this.columns = [
        {
          name: __("Document Type"),
          editable: false,
          width: 125
        },
        {
          name: __("Document Name"),
          editable: false,
          width: 1,
          format: (value, row) => {
            return frappe.form.formatters.Link(value, { options: row[2].content });
          }
        },
        {
          name: __("Reference Date"),
          editable: false,
          width: 120,
          format: frappe.form.formatters.Date
        },
        {
          name: __("Remaining"),
          editable: false,
          width: 100
        },
        {
          name: __("Reference Number"),
          editable: false,
          width: 200
        },
        {
          name: __("Party"),
          editable: false,
          width: 100
        }
      ];
    }
    format_row(row) {
      return [
        row["doctype"],
        row["name"],
        row["reference_date"] || row["posting_date"],
        format_currency(row["paid_amount"], row["currency"]),
        row["reference_no"],
        row["party"]
      ];
    }
    get_datatable(proposals_wrapper) {
      if (!this.datatable) {
        const datatable_options = {
          columns: this.columns,
          data: this.data,
          dynamicRowHeight: true,
          checkboxColumn: true,
          inlineFilters: true
        };
        this.datatable = new frappe.DataTable(proposals_wrapper.get(0), datatable_options);
      } else {
        this.datatable.refresh(this.data, this.columns);
        this.datatable.rowmanager.checkMap = [];
      }
    }
    make_dialog() {
      const me = this;
      me.selected_payment = null;
      const fields = [
        {
          label: __("Action"),
          fieldname: "action",
          fieldtype: "Select",
          options: `Match Against Voucher
Create Voucher
Update Bank Transaction`,
          default: "Match Against Voucher"
        },
        {
          fieldname: "column_break_4",
          fieldtype: "Column Break"
        },
        {
          label: __("Document Type"),
          fieldname: "document_type",
          fieldtype: "Select",
          options: `Payment Entry
Journal Entry`,
          default: "Payment Entry",
          depends_on: "eval:doc.action=='Create Voucher'"
        },
        {
          fieldtype: "Section Break",
          fieldname: "section_break_1",
          label: __("Filters"),
          depends_on: "eval:doc.action=='Match Against Voucher'"
        }
      ];
      frappe.call({
        method: "erpnext.accounts.doctype.bank_transaction.bank_transaction.get_doctypes_for_bank_reconciliation",
        callback: (r) => {
          $.each(r.message, (_i, entry) => {
            if (_i % 3 == 0) {
              fields.push({
                fieldtype: "Column Break"
              });
            }
            fields.push({
              fieldtype: "Check",
              label: entry,
              fieldname: frappe.scrub(entry),
              onchange: () => this.update_options()
            });
          });
          fields.push(...this.get_voucher_fields());
          me.dialog = new frappe.ui.Dialog({
            title: __("Reconcile the Bank Transaction"),
            fields,
            size: "large",
            primary_action: (values) => this.reconciliation_dialog_primary_action(values)
          });
        }
      });
    }
    get_voucher_fields() {
      return [
        {
          fieldtype: "Check",
          label: "Show Only Exact Amount",
          fieldname: "exact_match",
          onchange: () => this.update_options()
        },
        {
          fieldname: "column_break_5",
          fieldtype: "Column Break"
        },
        {
          fieldtype: "Check",
          label: "Bank Transaction",
          fieldname: "bank_transaction",
          onchange: () => this.update_options()
        },
        {
          fieldtype: "Section Break",
          fieldname: "section_break_1",
          label: __("Select Vouchers to Match"),
          depends_on: "eval:doc.action=='Match Against Voucher'"
        },
        {
          fieldtype: "HTML",
          fieldname: "payment_proposals"
        },
        {
          fieldtype: "HTML",
          fieldname: "no_matching_vouchers",
          options: __('<div class="text-muted text-center">{0}</div>', [
            __("No Matching Vouchers Found")
          ])
        },
        {
          fieldtype: "Section Break",
          fieldname: "details",
          label: "Details",
          depends_on: "eval:doc.action!='Match Against Voucher'"
        },
        {
          fieldname: "reference_number",
          fieldtype: "Data",
          label: "Reference Number",
          mandatory_depends_on: "eval:doc.action=='Create Voucher'"
        },
        {
          default: "Today",
          fieldname: "posting_date",
          fieldtype: "Date",
          label: "Posting Date",
          reqd: 1,
          depends_on: "eval:doc.action=='Create Voucher'"
        },
        {
          fieldname: "reference_date",
          fieldtype: "Date",
          label: "Cheque/Reference Date",
          mandatory_depends_on: "eval:doc.action=='Create Voucher'",
          depends_on: "eval:doc.action=='Create Voucher'",
          reqd: 1
        },
        {
          fieldname: "mode_of_payment",
          fieldtype: "Link",
          label: "Mode of Payment",
          options: "Mode of Payment",
          depends_on: "eval:doc.action=='Create Voucher'"
        },
        {
          fieldname: "edit_in_full_page",
          fieldtype: "Button",
          label: "Edit in Full Page",
          click: () => {
            this.edit_in_full_page();
          },
          depends_on: "eval:doc.action=='Create Voucher'"
        },
        {
          fieldname: "column_break_7",
          fieldtype: "Column Break"
        },
        {
          default: "Bank Entry",
          fieldname: "journal_entry_type",
          fieldtype: "Select",
          label: "Journal Entry Type",
          options: "Journal Entry\nInter Company Journal Entry\nBank Entry\nCash Entry\nCredit Card Entry\nDebit Note\nCredit Note\nContra Entry\nExcise Entry\nWrite Off Entry\nOpening Entry\nDepreciation Entry\nExchange Rate Revaluation\nDeferred Revenue\nDeferred Expense",
          depends_on: "eval:doc.action=='Create Voucher' &&  doc.document_type=='Journal Entry'",
          mandatory_depends_on: "eval:doc.action=='Create Voucher' &&  doc.document_type=='Journal Entry'"
        },
        {
          fieldname: "second_account",
          fieldtype: "Link",
          label: "Account",
          options: "Account",
          depends_on: "eval:doc.action=='Create Voucher' &&  doc.document_type=='Journal Entry'",
          mandatory_depends_on: "eval:doc.action=='Create Voucher' &&  doc.document_type=='Journal Entry'",
          get_query: () => {
            return {
              filters: {
                is_group: 0,
                company: this.company
              }
            };
          }
        },
        {
          fieldname: "party_type",
          fieldtype: "Link",
          label: "Party Type",
          options: "DocType",
          mandatory_depends_on: "eval:doc.action=='Create Voucher' &&  doc.document_type=='Payment Entry'",
          get_query: function() {
            return {
              filters: {
                name: ["in", Object.keys(frappe.boot.party_account_types)]
              }
            };
          }
        },
        {
          fieldname: "party",
          fieldtype: "Dynamic Link",
          label: "Party",
          options: "party_type",
          mandatory_depends_on: "eval:doc.action=='Create Voucher' && doc.document_type=='Payment Entry'"
        },
        {
          fieldname: "project",
          fieldtype: "Link",
          label: "Project",
          options: "Project",
          depends_on: "eval:doc.action=='Create Voucher' && doc.document_type=='Payment Entry'"
        },
        {
          fieldname: "cost_center",
          fieldtype: "Link",
          label: "Cost Center",
          options: "Cost Center",
          depends_on: "eval:doc.action=='Create Voucher' && doc.document_type=='Payment Entry'",
          get_query: () => {
            return {
              filters: {
                is_group: 0,
                company: this.company
              }
            };
          }
        },
        {
          fieldtype: "Section Break",
          fieldname: "details_section",
          label: "Transaction Details"
        },
        {
          fieldname: "date",
          fieldtype: "Date",
          label: "Date",
          read_only: 1
        },
        {
          fieldname: "deposit",
          fieldtype: "Currency",
          label: "Deposit",
          options: "account_currency",
          read_only: 1
        },
        {
          fieldname: "withdrawal",
          fieldtype: "Currency",
          label: "Withdrawal",
          options: "account_currency",
          read_only: 1
        },
        {
          fieldname: "column_break_17",
          fieldtype: "Column Break",
          read_only: 1
        },
        {
          fieldname: "description",
          fieldtype: "Small Text",
          label: "Description",
          read_only: 1
        },
        {
          fieldname: "allocated_amount",
          fieldtype: "Currency",
          label: "Allocated Amount",
          options: "account_currency",
          read_only: 1
        },
        {
          fieldname: "unallocated_amount",
          fieldtype: "Currency",
          label: "Unallocated Amount",
          options: "account_currency",
          read_only: 1
        },
        {
          fieldname: "account_currency",
          fieldtype: "Link",
          label: "Currency",
          options: "Currency",
          read_only: 1,
          hidden: 1
        }
      ];
    }
    get_selected_attributes() {
      let selected_attributes = [];
      this.dialog.$wrapper.find(".checkbox input").each((i, col) => {
        if ($(col).is(":checked")) {
          selected_attributes.push($(col).attr("data-fieldname"));
        }
      });
      return selected_attributes;
    }
    update_options() {
      let selected_attributes = this.get_selected_attributes();
      this.get_linked_vouchers(selected_attributes);
    }
    reconciliation_dialog_primary_action(values) {
      if (values.action == "Match Against Voucher")
        this.match(values);
      if (values.action == "Create Voucher" && values.document_type == "Payment Entry")
        this.add_payment_entry(values);
      if (values.action == "Create Voucher" && values.document_type == "Journal Entry")
        this.add_journal_entry(values);
      else if (values.action == "Update Bank Transaction")
        this.update_transaction(values);
    }
    match() {
      var selected_map = this.datatable.rowmanager.checkMap;
      let rows = [];
      selected_map.forEach((val, index) => {
        if (val == 1)
          rows.push(this.datatable.datamanager.rows[index]);
      });
      let vouchers = [];
      rows.forEach((x) => {
        vouchers.push({
          payment_doctype: x[2].content,
          payment_name: x[3].content,
          amount: x[5].content
        });
      });
      frappe.call({
        method: "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.reconcile_vouchers",
        args: {
          bank_transaction_name: this.bank_transaction.name,
          vouchers
        },
        callback: (response) => {
          const alert_string = __("Bank Transaction {0} Matched", [this.bank_transaction.name]);
          frappe.show_alert(alert_string);
          this.update_dt_cards(response.message);
          this.dialog.hide();
        }
      });
    }
    add_payment_entry(values) {
      frappe.call({
        method: "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.create_payment_entry_bts",
        args: {
          bank_transaction_name: this.bank_transaction.name,
          reference_number: values.reference_number,
          reference_date: values.reference_date,
          party_type: values.party_type,
          party: values.party,
          posting_date: values.posting_date,
          mode_of_payment: values.mode_of_payment,
          project: values.project,
          cost_center: values.cost_center
        },
        callback: (response) => {
          const alert_string = __("Bank Transaction {0} added as Payment Entry", [
            this.bank_transaction.name
          ]);
          frappe.show_alert(alert_string);
          this.update_dt_cards(response.message);
          this.dialog.hide();
        }
      });
    }
    add_journal_entry(values) {
      frappe.call({
        method: "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.create_journal_entry_bts",
        args: {
          bank_transaction_name: this.bank_transaction.name,
          reference_number: values.reference_number,
          reference_date: values.reference_date,
          party_type: values.party_type,
          party: values.party,
          posting_date: values.posting_date,
          mode_of_payment: values.mode_of_payment,
          entry_type: values.journal_entry_type,
          second_account: values.second_account
        },
        callback: (response) => {
          const alert_string = __("Bank Transaction {0} added as Journal Entry", [
            this.bank_transaction.name
          ]);
          frappe.show_alert(alert_string);
          this.update_dt_cards(response.message);
          this.dialog.hide();
        }
      });
    }
    update_transaction(values) {
      frappe.call({
        method: "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.update_bank_transaction",
        args: {
          bank_transaction_name: this.bank_transaction.name,
          reference_number: values.reference_number,
          party_type: values.party_type,
          party: values.party
        },
        callback: (response) => {
          const alert_string = __("Bank Transaction {0} updated", [this.bank_transaction.name]);
          frappe.show_alert(alert_string);
          this.update_dt_cards(response.message);
          this.dialog.hide();
        }
      });
    }
    edit_in_full_page() {
      const values = this.dialog.get_values(true);
      if (values.document_type == "Payment Entry") {
        frappe.call({
          method: "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.create_payment_entry_bts",
          args: {
            bank_transaction_name: this.bank_transaction.name,
            reference_number: values.reference_number,
            reference_date: values.reference_date,
            party_type: values.party_type,
            party: values.party,
            posting_date: values.posting_date,
            mode_of_payment: values.mode_of_payment,
            project: values.project,
            cost_center: values.cost_center,
            allow_edit: true
          },
          callback: (r) => {
            const doc = frappe.model.sync(r.message);
            frappe.set_route("Form", doc[0].doctype, doc[0].name);
          }
        });
      } else {
        frappe.call({
          method: "erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.create_journal_entry_bts",
          args: {
            bank_transaction_name: this.bank_transaction.name,
            reference_number: values.reference_number,
            reference_date: values.reference_date,
            party_type: values.party_type,
            party: values.party,
            posting_date: values.posting_date,
            mode_of_payment: values.mode_of_payment,
            entry_type: values.journal_entry_type,
            second_account: values.second_account,
            allow_edit: true
          },
          callback: (r) => {
            var doc = frappe.model.sync(r.message);
            frappe.set_route("Form", doc[0].doctype, doc[0].name);
          }
        });
      }
    }
  };
})();
//# sourceMappingURL=bank-reconciliation-tool.bundle.G7MHMAFO.js.map

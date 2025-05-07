import frappe

class CurrencyExchangeManager:
    # Default exchange rates for common currency pairs (optional fallback)
    DEFAULT_RATES = {
        ("MGA", "EUR"): 0.00022,  # Approximate rate for MGA to EUR
        ("USD", "EUR"): 0.95,     # Approximate rate for USD to EUR
        ("USD", "MGA"): 4500,     # Approximate rate for USD to MGA
        ("EUR", "MGA"): 4500      # Approximate rate for EUR to MGA
    }

    @staticmethod
    def ensure_currency_exchange(from_currency, to_currency, date=None):
        """
        Ensure a Currency Exchange record exists for the given currency pair and return its exchange rate.

        Args:
            from_currency (str): Source currency (e.g., 'MGA', 'USD').
            to_currency (str): Target currency (e.g., 'EUR', 'MGA').
            date (str, optional): Date for the exchange rate (defaults to today).

        Returns:
            float: The exchange rate for the currency pair.

        Raises:
            frappe.exceptions.ValidationError: If currencies are invalid or rate cannot be determined.
        """
        if not from_currency or not to_currency:
            frappe.throw(_("Source and target currencies are required."))

        # If same currency, return 1.0
        if from_currency == to_currency:
            return 1.0

        # Use today's date if none provided
        date = date or frappe.utils.nowdate()

        # Check if Currency Exchange record exists
        exchange_record = frappe.db.get_value(
            "Currency Exchange",
            {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "date": ["<=", date]
            },
            ["exchange_rate"],
            order_by="date desc"
        )

        if exchange_record:
            frappe.log_error(
                f"Found existing Currency Exchange for {from_currency} to {to_currency}: {exchange_record}",
                "Debug CurrencyExchangeManager"
            )
            return exchange_record

        exchange_rate = CurrencyExchangeManager.DEFAULT_RATES.get((from_currency, to_currency), 1.0)

        # Verify currencies exist in Currency doctype
        for currency in [from_currency, to_currency]:
            if not frappe.db.exists("Currency", currency):
                frappe.log_error(f"Creating currency {currency}", "Debug CurrencyExchangeManager")
                currency_doc = frappe.get_doc({
                    "doctype": "Currency",
                    "name": currency,
                    "currency_name": currency  # Fallback name; ideally fetch from country_info
                })
                currency_doc.insert()
                frappe.db.commit()
                frappe.msgprint(_(f"Currency {currency} créé avec succès"))

        # Create Currency Exchange record
        frappe.log_error(
            f"Creating Currency Exchange for {from_currency} to {to_currency} with rate {exchange_rate}",
            "Debug CurrencyExchangeManager"
        )
        exchange_doc = frappe.get_doc({
            "doctype": "Currency Exchange",
            "from_currency": from_currency,
            "to_currency": to_currency,
            "exchange_rate": 1,
            "date": date
        })
        exchange_doc.insert()
        frappe.db.commit()
        frappe.msgprint(_(f"Currency Exchange {from_currency} to {to_currency} créé avec succès"))

        return exchange_rate
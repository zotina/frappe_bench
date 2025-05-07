# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

class CountryNormalizer:
    # Country mapping dictionary for normalizing country names
    COUNTRY_MAPPING = {
        "usa": "United States",
        "madagascar": "Madagascar",
        "uk": "United Kingdom",
        "us": "United States",
        "united states of america": "United States",
        # Add more mappings as needed
    }

    @staticmethod
    def normalize_country(country_name):
        """
        Normalize a country name to a standard format.

        Args:
            country_name (str): The country name to normalize.

        Returns:
            str: The normalized country name, or the original name if no mapping exists.
        """
        if not country_name:
            return country_name
        # Convert to lowercase for case-insensitive matching
        country_key = country_name.lower()
        # Return mapped value or original name if no mapping exists
        return CountryNormalizer.COUNTRY_MAPPING.get(country_key, country_name)
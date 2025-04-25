import csv
import frappe
from frappe.utils import getdate, get_datetime, get_time
from datetime import datetime
from io import StringIO

class CsvService:
    @staticmethod
    def import_csv(file_content, doctype):
        result_list = []
        error_list = []
        line_number = 1  # Start from 1 for header row

        print(f"Starting CSV parsing for doctype: {doctype}")

        try:
            print(f"Decoding file content (size: {len(file_content)} bytes)")
            reader = StringIO(file_content.decode('utf-8') if isinstance(file_content, bytes) else file_content)
            csv_reader = csv.DictReader(reader)
            doctype_fields = {field.fieldname: field.fieldtype for field in frappe.get_meta(doctype).fields}

            print(f"Doctype fields: {list(doctype_fields.keys())}")
            print(f"CSV headers: {csv_reader.fieldnames}")

            for row in csv_reader:
                line_number += 1  # Increment for each data row
                print(f"Processing row {line_number}: {row}")
                row_errors = []
                record = {}
                doc = None

                # Create a new Teste doctype instance
                try:
                    doc = frappe.get_doc({"doctype": doctype})
                except Exception as e:
                    row_errors.append(f"Failed to create doctype instance: {str(e)}")
                    print(f"Error creating doctype instance for row {line_number}: {str(e)}")

                if doc:
                    # Validate field values using doc.validate
                    for fieldname, value in row.items():
                        if fieldname in doctype_fields and value:
                            try:
                                parsed_value = CsvService.parse_value(doctype_fields[fieldname], value)
                                if parsed_value is None:
                                    row_errors.append(f"Field '{fieldname}' with value '{value}' could not be parsed for type '{doctype_fields[fieldname]}'")
                                else:
                                    # Call non-static validate method on doc instance
                                    try:
                                        doc.validateAll(fieldname, parsed_value)
                                        record[fieldname] = parsed_value
                                        print(f"Mapped field {fieldname} with value: {parsed_value}")
                                    except Exception as e:
                                        error_list.append({
                                            "line": line_number,
                                            "error_message": str(e),
                                            "data": row
                                        })
                            except Exception as e:
                                error_list.append({
                                    "line": line_number,
                                    "error_message": str(e),
                                    "data": row
                                })

                # If there are errors, add to error_list
                if record:  # Only add if record contains parsed values
                    result_list.append(record)
                    print(f"Added record to result list: {record}")
                    
            print(f"CSV parsing completed. Total records parsed: {len(result_list)}, Errors: {len(error_list)}")
            return error_list, result_list

        except Exception as e:
            print(f"Error parsing CSV: {str(e)}")
            error_list.append({
                "line": 1,
                "error_message": f"Failed to parse CSV: {str(e)}",
                "data": {}
            })
            return error_list, result_list

    @staticmethod
    def parse_value(field_type, value):
        print(f"Parsing value '{value}' for field type: {field_type}")
        try:
            if field_type in ['Int', 'Integer']:
                return int(value)
            elif field_type in ['Float', 'Currency', 'Percent']:
                return float(value)
            elif field_type == 'Check':
                return 1 if value.lower() in ['true', '1', 'yes'] else 0
            elif field_type in ['Data', 'Long Text']:
                return value
            elif field_type == 'Text':
                return value
            elif field_type == 'Date':
                parsed_date = getdate(value)
                print(f"Parsed date: {parsed_date}")
                return parsed_date
            elif field_type == 'Datetime':
                return get_datetime(value)
            elif field_type == 'Time':
                return get_time(value)
            elif field_type == 'Link':
                return value
            elif field_type == 'Select':
                return value
            elif field_type in ['Table', 'Table MultiSelect']:
                parsed_list = [v.strip() for v in value.split(',')]
                print(f"Parsed list: {parsed_list}")
                return parsed_list
            else:
                print(f"Unsupported field type: {field_type}")
                return value
        except Exception as e:
            print(f"Error parsing value '{value}' for type '{field_type}': {str(e)}")
            return None
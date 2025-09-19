"""
This script was used to make the "combined_data.sqlite" file that is used in the data
frames integration tests.
"""

import csv
import glob
import os
import sqlite3
from pathlib import Path


def get_csv_files(directory):
    """Get all CSV files in the specified directory."""
    csv_pattern = os.path.join(directory, "*.csv")
    return glob.glob(csv_pattern)


def get_table_name_from_filename(csv_file):
    """Generate a table name from the CSV filename."""
    filename = Path(csv_file).stem
    # Replace hyphens and spaces with underscores, remove special characters
    table_name = "".join(c if c.isalnum() or c == "_" else "_" for c in filename)
    # Remove multiple consecutive underscores
    table_name = "_".join(filter(None, table_name.split("_")))
    return table_name.lower()


def get_column_type(value):
    """Determine the appropriate SQLite column type based on the value."""
    if value is None or value == "":
        return "TEXT"

    # Try to convert to integer
    try:
        int(value)
        return "INTEGER"
    except (ValueError, TypeError):
        pass

    # Try to convert to float
    try:
        float(value)
        return "REAL"
    except (ValueError, TypeError):
        pass

    # Default to TEXT
    return "TEXT"


def create_table_from_csv(cursor, csv_file, table_name):
    """Create a table based on the CSV structure."""
    with open(csv_file, encoding="utf-8") as csvfile:
        csv_reader = csv.DictReader(csvfile)

        # Get the first row to determine column types
        first_row = next(csv_reader, None)
        if not first_row:
            return False

        # Create column definitions
        columns = []
        for col_name, value in first_row.items():
            col_type = get_column_type(value)
            # Clean column name
            clean_col_name = "".join(c if c.isalnum() or c == "_" else "_" for c in col_name)
            clean_col_name = "_".join(filter(None, clean_col_name.split("_")))
            columns.append(f"{clean_col_name} {col_type}")

        # Create table
        create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {", ".join(columns)}
            )
        """
        cursor.execute(create_sql)
        return True


def insert_csv_data(cursor, csv_file, table_name):
    """Insert data from CSV into the table."""
    with open(csv_file, encoding="utf-8") as csvfile:
        csv_reader = csv.DictReader(csvfile)

        # Get column names from CSV
        csv_columns = csv_reader.fieldnames
        if not csv_columns:
            return 0

        # Clean column names to match table columns
        clean_columns = []
        for col in csv_columns:
            clean_col = "".join(c if c.isalnum() or c == "_" else "_" for c in col)
            clean_col = "_".join(filter(None, clean_col.split("_")))
            clean_columns.append(clean_col)

        # Create insert statement
        placeholders = ", ".join(["?" for _ in clean_columns])
        insert_sql = f"""
            INSERT INTO {table_name} ({", ".join(clean_columns)})
            VALUES ({placeholders})
        """

        rows_inserted = 0
        for row in csv_reader:
            # Convert values to appropriate types
            values = []
            for _col_name, value in row.items():
                if value is None or value == "":
                    values.append(None)
                else:
                    # Try to convert to appropriate type
                    try:
                        # Try integer first
                        if "." not in value:
                            try:
                                values.append(int(value))
                                continue
                            except ValueError:
                                pass
                        # Try float
                        values.append(float(value))
                    except (ValueError, TypeError):
                        # Keep as string
                        values.append(value)

            cursor.execute(insert_sql, values)
            rows_inserted += 1

        return rows_inserted


def main():
    """
    Make a sqlite database from CSV files in the current directory.
    """
    curdir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(curdir, "combined_data.sqlite")

    # Get all CSV files in the directory
    csv_files = get_csv_files(curdir)

    if not csv_files:
        print("No CSV files found in the directory.")
        return

    print(f"Found {len(csv_files)} CSV file(s):")
    for csv_file in csv_files:
        print(f"  - {os.path.basename(csv_file)}")

    # Create SQLite database
    conn = sqlite3.connect(output_file)
    cursor = conn.cursor()

    total_tables = 0
    total_rows = 0

    # Process each CSV file
    for csv_file in csv_files:
        table_name = get_table_name_from_filename(csv_file)
        print(f"\nProcessing: {os.path.basename(csv_file)} -> table '{table_name}'")

        try:
            # Create table
            if create_table_from_csv(cursor, csv_file, table_name):
                # Insert data
                rows_inserted = insert_csv_data(cursor, csv_file, table_name)
                print(f"  ✓ Created table '{table_name}' with {rows_inserted} rows")
                total_tables += 1
                total_rows += rows_inserted
            else:
                print(f"  ✗ Failed to create table for {os.path.basename(csv_file)}")
        except Exception as e:
            print(f"  ✗ Error processing {os.path.basename(csv_file)}: {e}")

    # Commit changes and close connection
    conn.commit()
    conn.close()

    print(f"\n✓ Successfully created SQLite database '{output_file}'")
    print(f"  - {total_tables} tables created")
    print(f"  - {total_rows} total rows inserted")


if __name__ == "__main__":
    main()

import sqlite3
import pandas as pd

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('data_insights.db')
cursor = conn.cursor()

# Drop tables if they exist
cursor.execute('DROP TABLE IF EXISTS sales_data')
cursor.execute('DROP TABLE IF EXISTS product_info')

# Create sales_data table
cursor.execute('''
CREATE TABLE IF NOT EXISTS sales_data (
    product_id INTEGER,
    sales_amount REAL,
    sale_date TEXT,
    region TEXT
)
''')

# Create product_info table
cursor.execute('''
CREATE TABLE IF NOT EXISTS product_info (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT,
    category TEXT,
    price REAL
)
''')

# Commit changes and close the connection
conn.commit()
conn.close()

print("Database and tables created successfully.")
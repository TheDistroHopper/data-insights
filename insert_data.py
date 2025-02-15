import sqlite3
import pandas as pd

# Connect to SQLite database
conn = sqlite3.connect('data_insights.db')

# Load data from CSV files
sales_data = pd.read_csv('sales_data.csv')
product_info = pd.read_csv('product_info.csv')

# Insert data into sales_data table
sales_data.to_sql('sales_data', conn, if_exists='append', index=False)

# Insert data into product_info table
product_info.to_sql('product_info', conn, if_exists='append', index=False)

# Commit changes and close the connection
conn.commit()
conn.close()

print("Data inserted successfully.")
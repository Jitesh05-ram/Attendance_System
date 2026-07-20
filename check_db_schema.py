import sqlite3

conn = sqlite3.connect('instance/database.db')
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables in database:")
for (table_name,) in tables:
    print(f"\n=== {table_name} ===")
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    for col in columns:
        print(col)

conn.close()

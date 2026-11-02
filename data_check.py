import sqlite3

conn = sqlite3.connect("file:data/chinook.db?mode=ro", uri=True)
cursor = conn.cursor()

query = """
DELETE FROM Customer
"""

cursor.execute(query)

for row in cursor.fetchall():
    print(row)

conn.close()
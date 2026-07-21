import sqlite3
conn = sqlite3.connect('local.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM skus')
rows = cursor.fetchall()
print(f"SKUs count: {len(rows)}")
for row in rows:
    print(row)

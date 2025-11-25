import sqlite3
from tabulate import tabulate

conn = sqlite3.connect("football.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM matches")
rows = cursor.fetchall()

print(tabulate(rows))

conn.close()
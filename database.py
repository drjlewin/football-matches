import sqlite3

# Connect (or create) the database
conn = sqlite3.connect("football.db")
cursor = conn.cursor()

# Create table for matches
cursor.execute("""
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    home_team TEXT,
    away_team TEXT,
    time TEXT,
    competition TEXT,
    channel TEXT
)
""")

conn.commit()
conn.close()

print("Database and table created successfully!")
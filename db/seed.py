import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "vendor_ai_tracker.db"


def seed():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO vendors (name, metadata) VALUES (?, ?)", ("Example Vendor", "{\"category\": \"software\"}"))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed()
    print("Seed data inserted into database.")

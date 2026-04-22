-- Database schema for Vendor AI Tracker
CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    company_name TEXT,
    rate TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

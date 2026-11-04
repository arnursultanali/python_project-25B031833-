import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

DDL = """
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    city        TEXT DEFAULT 'Almaty'
);

CREATE TABLE accounts (
    account_id     SERIAL PRIMARY KEY,
    customer_id    INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    account_number TEXT UNIQUE NOT NULL,
    balance        NUMERIC(15,2) NOT NULL DEFAULT 0.00 CHECK (balance >= 0)
);

CREATE TABLE transactions (
    transaction_id SERIAL PRIMARY KEY,
    account_id     INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    amount         NUMERIC(15,2) NOT NULL,
    tx_type        TEXT NOT NULL CHECK (tx_type IN ('DEBIT', 'CREDIT')),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SEED_CUSTOMERS = [
    ("Arman Bekov", "arman@kazbank.kz", "Almaty"),
    ("Zarina Seiit", "zarina@kazbank.kz", "Nur-Sultan"),
    ("Daniyar Nurlan", "daniyar@kazbank.kz", "Shymkent"),
    ("Aisha Omarova", "aisha@kazbank.kz", "Almaty"),
    ("Kairat Nurtas", "kairat@kazbank.kz", "Astana"),
    ("Elena Kim", "elena@kazbank.kz", "Almaty"),
    ("Miras Zhakupov", "miras@kazbank.kz", "Karaganda"),
    ("Dinara Saparova", "dinara@kazbank.kz", "Aktobe"),
    ("Bauyrzhan Isa", "bauyrzhan@kazbank.kz", "Almaty"),
    ("Dana Sadykova", "dana@kazbank.kz", "Shymkent")
]

SEED_ACCOUNTS = [
    (1, "KZ1001", 150000.00),
    (1, "KZ1002", 50000.00),
    (2, "KZ2001", 300000.00),
    (3, "KZ3001", 75000.00),
    (4, "KZ4001", 120000.00),
    (4, "KZ4002", 10000.00),
    (5, "KZ5001", 500000.00),
    (6, "KZ6001", 200000.00),
    (7, "KZ7001", 90000.00),
    (8, "KZ8001", 450000.00),
    (9, "KZ9001", 110000.00),
    (10, "KZ10001", 65000.00),
    (2, "KZ2002", 20000.00),
    (3, "KZ3002", 15000.00),
    (5, "KZ5002", 80000.00)
]

def init_db():
    print("Инициализация базы данных KazBank...")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            
            cur.executemany(
                "INSERT INTO customers (full_name, email, city) VALUES (%s, %s, %s)",
                SEED_CUSTOMERS
            )
            
            cur.executemany(
                "INSERT INTO accounts (customer_id, account_number, balance) VALUES (%s, %s, %s)",
                SEED_ACCOUNTS
            )
            conn.commit()
    print("Схема успешно создана и заполнена тестовыми данными!")

if __name__ == "__main__":
    init_db()
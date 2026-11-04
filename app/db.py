# app/db.py
import os
import time
import psycopg
from psycopg_pool import ConnectionPool
from psycopg import errors as pg_errors
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Пул подключений создается один раз при запуске приложения
pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=2,
    max_size=8,
    timeout=5.0
)

def get_pool():
    return pool

def with_retry(fn, max_retries=3):
    """Повторяет транзакцию при ошибке SerializationFailure (40001)."""
    for attempt in range(max_retries):
        try:
            return fn()
        except pg_errors.SerializationFailure:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.05 * (attempt + 1))
    raise RuntimeError("Превышено максимальное количество попыток повтора транзакции")
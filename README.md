# KazBank REST API

REST API сервис для банковской системы KazBank, разработанный на Python (Flask) и PostgreSQL с использованием библиотеки `psycopg3`.

---

## Технологический стек

* **Язык программирования:** Python 3.10+
* **Фреймворк:** Flask
* **База данных:** PostgreSQL 15+
* **Драйвер БД & Пулинг:** `psycopg3` (`psycopg[binary]`), `psycopg-pool`
* **Переменные окружения:** `python-dotenv`

---

## 🚀 Пошаговая инструкция по запуску

### 1. Клонирование и переход в папку проекта
```bash
git clone <https://github.com/arnursultanali>
cd python_project/<25B031833>/

Создание и активация виртуального окружения
# macOS / Linux:
python3 -m venv .venv
source .venv/bin/activate

Установка зависимостей
pip install -r requirements.txt

Настройка переменных окружения (.env)
DATABASE_URL=postgresql://postgres:secret@localhost:5432/kazbank

Инициализация базы данных и заполнением данными
python init_db.py

Запуск сервера Flask
python app.py
Сервер будет доступен по адресу: http://127.0.0.1:5000

примеры cURL-запросов
GET /health
curl -X GET [http://127.0.0.1:5000/health](http://127.0.0.1:5000/health)

GET /customers (поддерживает фильтрацию по городу ?city=Almaty)
curl -X GET "[http://127.0.0.1:5000/customers?city=Almaty](http://127.0.0.1:5000/customers?city=Almaty)"

POST /customers
curl -X POST [http://127.0.0.1:5000/customers](http://127.0.0.1:5000/customers) \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Arman Bekov", "email": "arman.bekov@example.com", "city": "Almaty"}'

GET /accounts?customer_id=<id>
curl -X GET "[http://127.0.0.1:5000/accounts?customer_id=1](http://127.0.0.1:5000/accounts?customer_id=1)"

POST /transfer
curl -X POST [http://127.0.0.1:5000/transfer](http://127.0.0.1:5000/transfer) \
  -H "Content-Type: application/json" \
  -d '{"from_account_id": 1, "to_account_id": 2, "amount": 5000}'

GET /transactions?account_id=<id>
curl -X GET "[http://127.0.0.1:5000/transactions?account_id=1](http://127.0.0.1:5000/transactions?account_id=1)"

Особенности реализации и безопасность
Пул подключений (ConnectionPool):
Создается один раз при старте приложения (min_size=2, max_size=8).
Исключает задержки на повторное открытие TCP-соединений с БД для каждого HTTP-запроса.

Гарантии ACID и уровень изоляции SERIALIZABLE:
Эндпоинт /transfer выполняется в строгой транзакции с уровнем изоляции SERIALIZABLE.
В случае ошибок конфликта транзакций (SerializationFailure / код 40001) применяется функция повторных попыток (with_retry) с экспоненциальной задержкой.

Защита от Deadlock (Взаимоблокировок):
При переводе средств account_id блокируются через FOR UPDATE в отсортированном порядке (sorted([from_acc, to_acc])), что исключает перекрестную блокировку процессов.

Защита от SQL-инъекций:
Все SQL-запросы используют параметризованные значения (%s), исключая прямой доступ через f-строки.

psycopg3 Cheat Sheet

# Connect
conn = psycopg.connect("host=... dbname=... user=... password=...")
 
# Execute a query
cur = conn.execute("SELECT ... FROM ... WHERE col = %s", (value,))
rows = cur.fetchall()   # list of tuples
row  = cur.fetchone()   # one tuple or None
 
# DML
conn.execute("INSERT INTO t (a,b) VALUES (%s,%s)", (a, b))
conn.execute("UPDATE t SET a=%s WHERE id=%s", (a, id))
conn.execute("DELETE FROM t WHERE id=%s", (id,))
conn.commit()   # or conn.rollback()
 
# Bulk insert
conn.executemany("INSERT INTO t (a) VALUES (%s)", [(1,),(2,),(3,)])
 
# SAVEPOINT
conn.execute("SAVEPOINT sp1")
conn.execute("ROLLBACK TO SAVEPOINT sp1")
conn.execute("RELEASE SAVEPOINT sp1")
 
# Isolation level
from psycopg import IsolationLevel
conn.isolation_level = IsolationLevel.SERIALIZABLE
 
# Pool
from psycopg_pool import ConnectionPool
pool = ConnectionPool(conninfo=..., min_size=2, max_size=10)
with pool.connection() as conn:
    conn.execute(...)

Обработка ошибок и HTTP-коды:
200 OK - Успешный GET или PUT
201 Created - Успешный POST, создающий ресурс
400 Bad Request — Неверный ввод (отсутствует поле, неверный тип)
404 Not Found - Ресурс не существует
409 Conflict — Нарушение ограничения из-за дублирования ключа
503 Service Unavailable — Ошибка подключения к базе данных.

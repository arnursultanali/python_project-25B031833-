import os
import time
from flask import Flask, request, jsonify
import psycopg
from psycopg import errors as pg_errors, IsolationLevel
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:secret@localhost:5432/kazbank")

# Инициализация пула подключений при старте приложения (R3)
pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=2,
    max_size=8,
    timeout=5.0
)

# Функция повторных попыток для SerializationFailure (R5)
def with_retry(fn, max_retries=3):
    for attempt in range(max_retries):
        try:
            return fn()
        except pg_errors.SerializationFailure:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.05 * (2 ** attempt))
    raise RuntimeError("Max retries exceeded")

# GET /health - Статистика пула подключений (R8)
@app.route("/health", methods=["GET"])
def health():
    try:
        pool.check()
        stats = pool.get_stats()
        return jsonify({"status": "ok", "pool_stats": stats}), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 503

# GET /customers и POST /customers (R2, R6, R7)
@app.route("/customers", methods=["GET", "POST"])
def handle_customers():
    if request.method == "GET":
        city = request.args.get("city")
        if city:
            sql = "SELECT customer_id, full_name, email, city FROM customers WHERE city = %s ORDER BY customer_id"
            args = (city,)
        else:
            sql = "SELECT customer_id, full_name, email, city FROM customers ORDER BY customer_id"
            args = ()
        
        with pool.connection() as conn:
            rows = conn.execute(sql, args).fetchall()
        return jsonify([{"id": r[0], "name": r[1], "email": r[2], "city": r[3]} for r in rows]), 200

    elif request.method == "POST":
        data = request.get_json(force=True)
        try:
            with pool.connection() as conn:
                cur = conn.execute(
                    "INSERT INTO customers (full_name, email, city) VALUES (%s, %s, %s) RETURNING customer_id",
                    (data.get("full_name"), data.get("email"), data.get("city", "Almaty"))
                )
                new_id = cur.fetchone()[0]
                conn.commit()
            return jsonify({"customer_id": new_id}), 201

        except pg_errors.UniqueViolation:
            return jsonify({"error": "Email already exists"}), 409
        except pg_errors.NotNullViolation as e:
            return jsonify({"error": f"Missing required field: {e.diag.column_name}"}), 400
        except psycopg.OperationalError:
            return jsonify({"error": "Database unavailable"}), 503

# GET /accounts?customer_id=n (R2)
@app.route("/accounts", methods=["GET"])
def list_accounts():
    customer_id = request.args.get("customer_id")
    if not customer_id:
        return jsonify({"error": "customer_id query parameter is required"}), 400
    
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT account_id, customer_id, account_number, balance FROM accounts WHERE customer_id = %s ORDER BY account_id",
            (customer_id,)
        ).fetchall()
    return jsonify([{"account_id": r[0], "customer_id": r[1], "account_number": r[2], "balance": float(r[3])} for r in rows]), 200

# GET /transactions?account_id=n (R2)
@app.route("/transactions", methods=["GET"])
def list_transactions():
    account_id = request.args.get("account_id")
    if not account_id:
        return jsonify({"error": "account_id query parameter is required"}), 400

    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT tx_id, account_id, amount, tx_type, created_at FROM transactions WHERE account_id = %s ORDER BY created_at DESC",
            (account_id,)
        ).fetchall()
    return jsonify([{"tx_id": r[0], "account_id": r[1], "amount": float(r[2]), "tx_type": r[3], "created_at": str(r[4])} for r in rows]), 200

# POST /transfer (R2, R4, R5)
@app.route("/transfer", methods=["POST"])
def transfer():
    data = request.get_json(force=True)
    from_acc = data.get("from_account_id")
    to_acc = data.get("to_account_id")
    amount = data.get("amount")

    if not from_acc or not to_acc or amount is None or amount <= 0:
        return jsonify({"error": "Invalid input parameters"}), 400

    def do_transfer():
        with pool.connection() as conn:
            conn.isolation_level = IsolationLevel.SERIALIZABLE
            
            # Предотвращение Deadlock: захват блокировок в упорядоченном по ID виде
            first_acc, second_acc = sorted([from_acc, to_acc])
            
            conn.execute("SELECT balance FROM accounts WHERE account_id = %s FOR UPDATE", (first_acc,))
            conn.execute("SELECT balance FROM accounts WHERE account_id = %s FOR UPDATE", (second_acc,))
            
            cur = conn.execute("SELECT balance FROM accounts WHERE account_id = %s", (from_acc,))
            row = cur.fetchone()
            if not row:
                raise ValueError("Sender account not found")
            if float(row[0]) < amount:
                raise ValueError("Insufficient balance")

            # Использование SAVEPOINT для частичного отката при сбоях
            conn.execute("SAVEPOINT sp_transfer")
            try:
                conn.execute(
                    "UPDATE accounts SET balance = balance - %s WHERE account_id = %s",
                    (amount, from_acc)
                )
                conn.execute(
                    "UPDATE accounts SET balance = balance + %s WHERE account_id = %s",
                    (amount, to_acc)
                )
                conn.execute(
                    "INSERT INTO transactions (account_id, amount, tx_type) VALUES (%s, %s, %s)",
                    (from_acc, -amount, "TRANSFER_OUT")
                )
                conn.execute(
                    "INSERT INTO transactions (account_id, amount, tx_type) VALUES (%s, %s, %s)",
                    (to_acc, amount, "TRANSFER_IN")
                )
                conn.commit()
            except Exception:
                conn.execute("ROLLBACK TO SAVEPOINT sp_transfer")
                conn.rollback()
                raise

    try:
        with_retry(do_transfer)
        return jsonify({"message": "Transfer completed successfully"}), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except pg_errors.UniqueViolation:
        return jsonify({"error": "Duplicate entry"}), 409
    except pg_errors.NotNullViolation as e:
        return jsonify({"error": f"Missing required field: {e.diag.column_name}"}), 400
    except psycopg.OperationalError:
        return jsonify({"error": "Database unavailable"}), 503
    except Exception as e:
        return jsonify({"error": f"Transfer failed: {str(e)}"}), 500
    
@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": "KazBank REST API is running",
        "available_endpoints": [
            "GET /health",
            "GET /customers",
            "POST /customers",
            "GET /accounts?customer_id=<id>",
            "GET /transactions?account_id=<id>",
            "POST /transfer"
        ]
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
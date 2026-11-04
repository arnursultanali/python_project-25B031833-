# app/routes/transactions.py
from flask import Blueprint, request, jsonify
import psycopg
from psycopg import errors as pg_errors
from app.db import pool

transactions_bp = Blueprint("transactions", __name__)

@transactions_bp.route("/transactions", methods=["GET"])
def get_transactions():
    account_id = request.args.get("account_id")
    if not account_id:
        return jsonify({"error": "Параметр account_id обязателен"}), 400

    try:
        with pool.connection() as conn:
            rows = conn.execute(
                "SELECT transaction_id, account_id, amount, tx_type, created_at FROM transactions WHERE account_id = %s ORDER BY created_at DESC",
                (account_id,)
            ).fetchall()
            
        result = [
            {
                "transaction_id": r[0],
                "account_id": r[1],
                "amount": float(r[2]),
                "tx_type": r[3],
                "created_at": r[4].isoformat() if r[4] else None
            } for r in rows
        ]
        return jsonify(result), 200

    except psycopg.OperationalError:
        return jsonify({"error": "База данных недоступна"}), 503

@transactions_bp.route("/transactions", methods=["POST"])
def create_transaction():
    data = request.get_json(force=True) or {}
    account_id = data.get("account_id")
    amount = data.get("amount")
    tx_type = data.get("tx_type")

    if not account_id or amount is None or tx_type not in ["DEBIT", "CREDIT"]:
        return jsonify({"error": "Некорректные данные транзакции"}), 400

    try:
        with pool.connection() as conn:
            # Проверка доступного остатка для операций снятия (DEBIT)[cite: 1]
            if tx_type == "DEBIT":
                cur = conn.execute("SELECT balance FROM accounts WHERE account_id = %s", (account_id,))
                row = cur.fetchone()
                if not row or row[0] < amount:
                    return jsonify({"error": "Недостаточно средств на счете"}), 400
                
                conn.execute("UPDATE accounts SET balance = balance - %s WHERE account_id = %s", (amount, account_id))
            else:
                conn.execute("UPDATE accounts SET balance = balance + %s WHERE account_id = %s", (amount, account_id))

            cur = conn.execute(
                "INSERT INTO transactions (account_id, amount, tx_type) VALUES (%s, %s, %s) RETURNING transaction_id",
                (account_id, amount, tx_type)
            )
            tx_id = cur.fetchone()[0]
            conn.commit()
            return jsonify({"transaction_id": tx_id, "status": "recorded"}), 201

    except pg_errors.ForeignKeyViolation:
        return jsonify({"error": "Счет с таким ID не существует"}), 400
    except psycopg.OperationalError:
        return jsonify({"error": "База данных недоступна"}), 503

@transactions_bp.route("/health", methods=["GET"])
def health_check():
    """Проверка доступности БД и возврат статистики пула[cite: 1]."""
    try:
        pool.check()
        stats = pool.get_stats()
        return jsonify({
            "status": "ok",
            "pool_stats": stats
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 503
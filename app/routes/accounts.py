# app/routes/accounts.py
from flask import Blueprint, request, jsonify
import psycopg
from psycopg import IsolationLevel, errors as pg_errors
from app.db import pool, with_retry

accounts_bp = Blueprint("accounts", __name__)

@accounts_bp.route("/accounts", methods=["GET"])
def get_accounts():
    customer_id = request.args.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Параметр customer_id обязателен"}), 400

    try:
        with pool.connection() as conn:
            rows = conn.execute(
                "SELECT account_id, customer_id, account_number, balance FROM accounts WHERE customer_id = %s ORDER BY account_id",
                (customer_id,)
            ).fetchall()
            
        result = [{"account_id": r[0], "customer_id": r[1], "account_number": r[2], "balance": float(r[3])} for r in rows]
        return jsonify(result), 200

    except psycopg.OperationalError:
        return jsonify({"error": "База данных недоступна"}), 503

@accounts_bp.route("/transfer", methods=["POST"])
def transfer_funds():
    data = request.get_json(force=True) or {}
    from_acc = data.get("from_account_id")
    to_acc = data.get("to_account_id")
    amount = data.get("amount")

    if not from_acc or not to_acc or amount is None or amount <= 0:
        return jsonify({"error": "Некорректные параметры перевода"}), 400

    def execute_transfer():
        with pool.connection() as conn:
            # Установка изоляции SERIALIZABLE для финансовых операций
            conn.isolation_level = IsolationLevel.SERIALIZABLE
            
            # Упорядочивание ID для предотвращения Deadlock
            first_id, second_id = sorted([from_acc, to_acc])
            
            # Явная блокировка строк FOR UPDATE
            conn.execute("SELECT balance FROM accounts WHERE account_id = %s FOR UPDATE", (first_id,))
            conn.execute("SELECT balance FROM accounts WHERE account_id = %s FOR UPDATE", (second_id,))

            # Проверка баланса отправителя
            cur = conn.execute("SELECT balance FROM accounts WHERE account_id = %s", (from_acc,))
            sender_row = cur.fetchone()
            if not sender_row:
                raise ValueError("Счет отправителя не найден")
            
            if sender_row[0] < amount:
                raise ValueError("Недостаточно средств на счете")

            # Использование SAVEPOINT для частичной защиты транзакции
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
                
                # Фиксация транзакции в журнале транзакций
                conn.execute(
                    "INSERT INTO transactions (account_id, amount, tx_type) VALUES (%s, %s, 'DEBIT')",
                    (from_acc, amount)
                )
                conn.execute(
                    "INSERT INTO transactions (account_id, amount, tx_type) VALUES (%s, %s, 'CREDIT')",
                    (to_acc, amount)
                )
                
                conn.commit() # Атомарное сохранение обоих изменений
                return {"status": "success", "message": "Перевод успешно выполнен"}
            except Exception:
                conn.execute("ROLLBACK TO SAVEPOINT sp_transfer") # Откат к точке сохранения[cite: 1]
                conn.rollback()
                raise

    try:
        # Оборачиваем вызов в с механизмом списания/повтора при конфликтах сериализации[cite: 1]
        res = with_retry(execute_transfer)
        return jsonify(res), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except pg_errors.SerializationFailure:
        return jsonify({"error": "Ошибка сериализации, попробуйте позже"}), 409
    except psycopg.OperationalError:
        return jsonify({"error": "База данных недоступна"}), 503
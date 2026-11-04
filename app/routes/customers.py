# app/routes/customers.py
from flask import Blueprint, request, jsonify
import psycopg
from psycopg import errors as pg_errors
from app.db import pool

customers_bp = Blueprint("customers", __name__)

@customers_bp.route("/customers", methods=["GET"])
def list_customers():
    city = request.args.get("city") # Фильтрация по Query parameter
    
    try:
        with pool.connection() as conn:
            if city:
                sql = "SELECT customer_id, full_name, email, city FROM customers WHERE city = %s ORDER BY customer_id"
                args = (city,)
            else:
                sql = "SELECT customer_id, full_name, email, city FROM customers ORDER BY customer_id"
                args = ()
            
            rows = conn.execute(sql, args).fetchall()
            
        result = [{"id": r[0], "name": r[1], "email": r[2], "city": r[3]} for r in rows]
        return jsonify(result), 200

    except psycopg.OperationalError:
        return jsonify({"error": "База данных недоступна"}), 503

@customers_bp.route("/customers", methods=["POST"])
def create_customer():
    data = request.get_json(force=True) or {}
    
    if "full_name" not in data or "email" not in data:
        return jsonify({"error": "Поля full_name и email обязательны"}), 400

    try:
        with pool.connection() as conn:
            cur = conn.execute(
                "INSERT INTO customers (full_name, email, city) VALUES (%s, %s, %s) RETURNING customer_id",
                (data["full_name"], data["email"], data.get("city", "Almaty"))
            )
            new_id = cur.fetchone()[0]
            conn.commit()
            return jsonify({"customer_id": new_id, "message": "Клиент успешно создан"}), 201

    except pg_errors.UniqueViolation:
        return jsonify({"error": "Пользователь с таким email уже существует"}), 409
    except pg_errors.NotNullViolation as e:
        return jsonify({"error": f"Отсутствует обязательное поле: {e.diag.column_name}"}), 400
    except psycopg.OperationalError:
        return jsonify({"error": "База данных недоступна"}), 503
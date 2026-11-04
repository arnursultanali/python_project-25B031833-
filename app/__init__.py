# app/__init__.py
from flask import Flask
from app.routes.customers import customers_bp
from app.routes.accounts import accounts_bp
from app.routes.transactions import transactions_bp

def create_app():
    app = Flask(__name__)

    # Регистрация блупринтов
    app.register_blueprint(customers_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(transactions_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
"""Configuração da aplicação Flask e recursos compartilhados pelos módulos."""

import hmac
import os
import secrets
from decimal import Decimal

from flask import Flask, abort, g, render_template, request, session

from .database import database_connection, init_db

app = Flask(__name__, template_folder="../templates", static_folder="../static")


# Configura sessões seguras e usa uma chave temporária quando não há uma definida no ambiente.
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
)


@app.before_request
def load_user_and_check_csrf():
    """Carrega o usuário da sessão e valida tokens CSRF em requisições POST."""
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        with database_connection() as conn:
            g.user = conn.execute(
                "SELECT id, name, email FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
        if g.user is None:
            session.clear()

    if request.method == "POST":
        supplied = request.form.get("csrf_token", "")
        expected = session.get("_csrf_token", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            abort(
                400,
                description="Token de segurança inválido. Atualize a página e tente novamente.",
            )


@app.context_processor
def template_context():
    """Disponibiliza usuário atual e gerador de token CSRF aos templates."""

    def csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_urlsafe(32)
        return session["_csrf_token"]

    return {"current_user": g.get("user"), "csrf_token": csrf_token}


@app.template_filter("brl")
def format_brl(value):
    """Formata valores numéricos no padrão monetário brasileiro."""
    amount = Decimal(value or 0)
    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


# Importa módulos para registrar suas rotas na aplicação Flask configurada acima.
from . import auth, dashboard, finance, movements, products, sales

__all__ = ["app", "init_db"]

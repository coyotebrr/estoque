"""Rotas de cadastro, autenticação e encerramento de sessão."""

import re

from flask import flash, g, redirect, render_template, request, session, url_for
from psycopg import errors
from werkzeug.security import check_password_hash, generate_password_hash

from . import app
from .database import database_connection
from .security import login_required


@app.route("/")
def index():
    """Redireciona a página inicial conforme o estado de autenticação."""
    return redirect(url_for("dashboard" if g.user else "login"))


@app.route("/cadastro", methods=["GET", "POST"])
def register():
    """Valida os dados enviados, cria uma conta e inicia a sessão do usuário."""
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirmation", "")

        if not name or len(name) > 120:
            flash("Informe seu nome (até 120 caracteres).", "error")
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
            flash("Informe um e-mail válido.", "error")
        elif len(password) < 8:
            flash("A senha precisa ter pelo menos 8 caracteres.", "error")
        elif password != confirmation:
            flash("As senhas não conferem.", "error")
        else:
            try:
                with database_connection() as conn:
                    user = conn.execute(
                        """
                        INSERT INTO users (name, email, password_hash)
                        VALUES (%s, %s, %s)
                        RETURNING id
                        """,
                        (name, email, generate_password_hash(password)),
                    ).fetchone()
            except errors.UniqueViolation:
                flash(
                    "Este e-mail já está cadastrado. Faça login ou use outro e-mail.",
                    "error",
                )
            else:
                session.clear()
                session["user_id"] = user["id"]
                flash("Conta criada. Boas-vindas ao seu estoque!", "success")
                return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Confere as credenciais e inicia uma sessão autenticada."""
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with database_connection() as conn:
            user = conn.execute(
                "SELECT id, password_hash FROM users WHERE LOWER(email) = %s",
                (email,),
            ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("E-mail ou senha incorretos.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/sair", methods=["POST"])
@login_required
def logout():
    """Encerra a sessão autenticada e retorna à tela de login."""
    session.clear()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("login"))

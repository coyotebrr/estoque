"""Decoradores e verificações reutilizáveis de acesso autenticado."""

from functools import wraps

from flask import flash, g, redirect, url_for


def login_required(view):
    """Impede acesso à rota quando não há usuário autenticado."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Entre na sua conta para continuar.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped

"""Rotas de consulta e manutenção do catálogo de produtos."""

from decimal import Decimal, InvalidOperation

from flask import abort, flash, g, redirect, render_template, request, url_for
from psycopg import errors

from . import app
from .database import database_connection
from .pricing import normalize_price
from .security import login_required


@app.route("/produtos")
@login_required
def products():
    """Lista produtos da conta atual e aplica o filtro de busca informado."""
    search = request.args.get("q", "").strip()[:100]
    with database_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, sku, category, unit, quantity, min_stock, cost_price, sale_price
            FROM products
            WHERE user_id = %s
              AND (%s = '' OR name ILIKE %s OR sku ILIKE %s OR category ILIKE %s)
            ORDER BY name ASC
            """,
            (g.user["id"], search, f"%{search}%", f"%{search}%", f"%{search}%"),
        ).fetchall()
    return render_template("products.html", products=rows, search=search)


@app.route("/produtos/novo", methods=["GET", "POST"])
@login_required
def new_product():
    """Exibe o formulário para cadastrar um produto."""
    return product_form()


@app.route("/produtos/<int:product_id>/editar", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    """Exibe o formulário preenchido para editar um produto existente."""
    return product_form(product_id)


@app.route("/produtos/<int:product_id>/excluir", methods=["POST"])
@login_required
def delete_product(product_id):
    """Exclui um produto pertencente ao usuário autenticado."""
    with database_connection() as conn:
        deleted_product = conn.execute(
            "DELETE FROM products WHERE id = %s AND user_id = %s RETURNING id",
            (product_id, g.user["id"]),
        ).fetchone()

    if deleted_product is None:
        abort(404)

    flash("Produto excluído com sucesso.", "success")
    return redirect(url_for("products"))


def product_form(product_id=None):
    """Valida e salva dados de produto, reutilizada no cadastro e na edição."""
    product = None
    if product_id is not None:
        with database_connection() as conn:
            product = conn.execute(
                "SELECT * FROM products WHERE id = %s AND user_id = %s",
                (product_id, g.user["id"]),
            ).fetchone()
        if product is None:
            abort(404)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip()
        category = request.form.get("category", "").strip()
        unit = request.form.get("unit", "").strip().upper() or "UN"
        min_stock_raw = request.form.get("min_stock", "0").strip()
        cost_price_raw = request.form.get("cost_price", "").strip().replace(",", ".")
        sale_price_raw = request.form.get("sale_price", "").strip().replace(",", ".")
        try:
            min_stock = int(min_stock_raw)
            cost_price = normalize_price(Decimal(cost_price_raw))
            sale_price = normalize_price(Decimal(sale_price_raw))
        except (ValueError, InvalidOperation):
            flash(
                "Confira o estoque mínimo, custo e preço de venda informados.", "error"
            )
        else:
            if not name or len(name) > 160:
                flash("O nome do produto é obrigatório (até 160 caracteres).", "error")
            elif len(sku) > 80 or len(category) > 100 or len(unit) > 30:
                flash("Confira o tamanho do código, categoria e unidade.", "error")
            elif min_stock < 0 or cost_price is None or sale_price is None:
                flash(
                    "Estoque mínimo, custo e preço de venda devem ser válidos e não negativos.",
                    "error",
                )
            else:
                try:
                    with database_connection() as conn:
                        if product_id is None:
                            conn.execute(
                                """
                                INSERT INTO products (user_id, name, sku, category, unit, min_stock, cost_price, sale_price)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    g.user["id"],
                                    name,
                                    sku,
                                    category,
                                    unit,
                                    min_stock,
                                    cost_price,
                                    sale_price,
                                ),
                            )
                        else:
                            conn.execute(
                                """
                                UPDATE products
                                SET name = %s, sku = %s, category = %s, unit = %s,
                                    min_stock = %s, cost_price = %s, sale_price = %s, updated_at = NOW()
                                WHERE id = %s AND user_id = %s
                                """,
                                (
                                    name,
                                    sku,
                                    category,
                                    unit,
                                    min_stock,
                                    cost_price,
                                    sale_price,
                                    product_id,
                                    g.user["id"],
                                ),
                            )
                except errors.UniqueViolation:
                    flash(
                        "Este código de produto já está sendo usado na sua conta.",
                        "error",
                    )
                else:
                    flash("Produto salvo com sucesso.", "success")
                    return redirect(url_for("products"))

    return render_template("product_form.html", product=product)

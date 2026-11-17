"""Registro e histórico das vendas realizadas."""

from flask import abort, flash, g, redirect, render_template, request, url_for

from . import app
from .constants import MAX_QUANTITY, PAYMENT_METHODS
from .database import database_connection
from .pricing import calculate_discount
from .security import login_required


@app.route("/vendas")
@login_required
def sales():
    """Lista o histórico de vendas sem expor os detalhes financeiros."""
    with database_connection() as conn:
        summary = conn.execute(
            """
            SELECT COUNT(*) AS sale_count
            FROM movements
            WHERE user_id = %s AND kind = 'OUT'
            """,
            (g.user["id"],),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT m.id, m.quantity, m.note, m.created_at, m.payment_method,
                   COALESCE(m.product_name_snapshot, p.name) AS product_name,
                   COALESCE(m.product_unit_snapshot, p.unit) AS unit
            FROM movements m
            LEFT JOIN products p ON p.id = m.product_id AND p.user_id = m.user_id
            WHERE m.user_id = %s AND m.kind = 'OUT'
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT 100
            """,
            (g.user["id"],),
        ).fetchall()
    return render_template("sales.html", sales=rows, summary=summary)


@app.route("/vendas/nova", methods=["GET", "POST"])
@login_required
def new_sale():
    """Registra uma venda, aplica desconto e reduz o estoque de forma transacional."""
    selected_product_id = request.values.get("product_id", type=int)
    with database_connection() as conn:
        product_rows = conn.execute(
            """
            SELECT id, name, sku, quantity, unit, cost_price, sale_price
            FROM products
            WHERE user_id = %s
            ORDER BY name ASC
            """,
            (g.user["id"],),
        ).fetchall()
        products_by_id = {row["id"]: row for row in product_rows}

    if request.method == "POST":
        selected_product_id = request.form.get("product_id", type=int)
        quantity_raw = request.form.get("quantity", "").strip()
        payment_method = request.form.get("payment_method", "")
        discount_type = request.form.get("discount_type", "AMOUNT")
        discount_value_raw = request.form.get("discount_value", "0").strip()
        note = request.form.get("note", "").strip()
        try:
            quantity = int(quantity_raw)
        except ValueError:
            quantity = 0
        validation_error = None
        if selected_product_id not in products_by_id:
            validation_error = "Selecione um produto válido."
        elif quantity <= 0 or quantity > MAX_QUANTITY:
            validation_error = (
                "A quantidade precisa ser um número inteiro maior que zero."
            )
        elif payment_method not in PAYMENT_METHODS:
            validation_error = "Selecione um método de pagamento válido."
        elif len(note) > 240:
            validation_error = "A observação pode ter até 240 caracteres."

        if validation_error:
            flash(validation_error, "error")
        else:
            with database_connection() as conn:
                product = conn.execute(
                    """
                    SELECT id, name, quantity, unit, cost_price, sale_price
                    FROM products
                    WHERE id = %s AND user_id = %s
                    FOR UPDATE
                    """,
                    (selected_product_id, g.user["id"]),
                ).fetchone()
                if product is None:
                    abort(404)
                if product["sale_price"] is None:
                    flash(
                        "Cadastre o preço de venda deste produto antes de registrar a venda.",
                        "error",
                    )
                elif quantity > product["quantity"]:
                    flash("Estoque insuficiente para completar o pedido.", "error")
                else:
                    sale_unit_price = product["sale_price"]
                    discount_value, discount_amount, discount_error = (
                        calculate_discount(
                            discount_type,
                            discount_value_raw,
                            sale_unit_price * quantity,
                        )
                    )
                    if discount_error:
                        flash(discount_error, "error")
                    else:
                        conn.execute(
                            """
                            INSERT INTO movements (
                                user_id, product_id, kind, quantity, note,
                                cost_unit_price, sale_unit_price, payment_method,
                                discount_type, discount_value, discount_amount,
                                product_name_snapshot, product_unit_snapshot
                            )
                            VALUES (%s, %s, 'OUT', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                g.user["id"],
                                product["id"],
                                quantity,
                                note,
                                product["cost_price"],
                                sale_unit_price,
                                payment_method,
                                discount_type,
                                discount_value,
                                discount_amount,
                                product["name"],
                                product["unit"],
                            ),
                        )
                        conn.execute(
                            """
                            UPDATE products SET quantity = quantity - %s, updated_at = NOW()
                            WHERE id = %s AND user_id = %s
                            """,
                            (quantity, product["id"], g.user["id"]),
                        )
                        flash(
                            "Venda registrada e estoque atualizado com sucesso.",
                            "success",
                        )
                        return redirect(url_for("sales"))

    return render_template(
        "sale_form.html",
        products=product_rows,
        selected_product_id=selected_product_id,
        payment_methods=PAYMENT_METHODS,
    )

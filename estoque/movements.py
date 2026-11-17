"""Registro, consulta, edição e remoção de movimentações do estoque."""

from decimal import Decimal, InvalidOperation

from flask import abort, flash, g, redirect, render_template, request, url_for

from . import app
from .constants import MAX_QUANTITY, PAYMENT_METHODS
from .database import database_connection
from .pricing import calculate_discount, normalize_price
from .security import login_required


@app.route("/movimentacoes/nova", methods=["GET", "POST"])
@login_required
def new_movement():
    """Registra uma entrada e aumenta o saldo do produto selecionado."""
    selected_product_id = request.values.get("product_id", type=int)
    with database_connection() as conn:
        product_rows = conn.execute(
            """
            SELECT id, name, sku, quantity, unit
            FROM products WHERE user_id = %s
            ORDER BY name ASC
            """,
            (g.user["id"],),
        ).fetchall()
        products_by_id = {row["id"]: row for row in product_rows}

    if request.method == "POST":
        selected_product_id = request.form.get("product_id", type=int)
        kind = request.form.get("kind", "")
        quantity_raw = request.form.get("quantity", "").strip()
        note = request.form.get("note", "").strip()
        try:
            quantity = int(quantity_raw)
        except ValueError:
            quantity = 0

        if selected_product_id not in products_by_id:
            flash("Selecione um produto válido.", "error")
        elif kind != "IN":
            flash("Saídas devem ser registradas na área de vendas.", "error")
        elif quantity <= 0:
            flash("A quantidade precisa ser um número inteiro maior que zero.", "error")
        elif len(note) > 240:
            flash("A observação pode ter até 240 caracteres.", "error")
        else:
            with database_connection() as conn:
                product = conn.execute(
                    """
                    SELECT id, name, quantity, unit, cost_price
                    FROM products
                    WHERE id = %s AND user_id = %s
                    FOR UPDATE
                    """,
                    (selected_product_id, g.user["id"]),
                ).fetchone()
                if product is None:
                    abort(404)
                conn.execute(
                    """
                    INSERT INTO movements (
                        user_id, product_id, kind, quantity, note,
                        product_name_snapshot, product_unit_snapshot
                    )
                    VALUES (%s, %s, 'IN', %s, %s, %s, %s)
                    """,
                    (
                        g.user["id"],
                        selected_product_id,
                        quantity,
                        note,
                        product["name"],
                        product["unit"],
                    ),
                )
                conn.execute(
                    """
                    UPDATE products SET quantity = quantity + %s, updated_at = NOW()
                    WHERE id = %s AND user_id = %s
                    """,
                    (quantity, selected_product_id, g.user["id"]),
                )
                flash("Entrada registrada com sucesso.", "success")
                return redirect(url_for("movements"))

    return render_template(
        "movement_form.html",
        products=product_rows,
        selected_product_id=selected_product_id,
    )


@app.route("/movimentacoes")
@login_required
def movements():
    """Exibe as entradas e saídas mais recentes sem valores financeiros."""
    with database_connection() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.kind, m.quantity, m.note, m.created_at,
                   COALESCE(m.product_name_snapshot, p.name) AS product_name,
                   COALESCE(m.product_unit_snapshot, p.unit) AS unit
            FROM movements m
            LEFT JOIN products p ON p.id = m.product_id AND p.user_id = m.user_id
            WHERE m.user_id = %s
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT 100
            """,
            (g.user["id"],),
        ).fetchall()
    return render_template("movements.html", movements=rows)


@app.route("/movimentacoes/<int:movement_id>/editar", methods=["GET", "POST"])
@login_required
def edit_movement(movement_id):
    """Atualiza uma movimentação e recalcula saldo e valores financeiros da venda."""
    with database_connection() as conn:
        movement = conn.execute(
            """
            SELECT m.*, p.id AS active_product_id, p.quantity AS product_quantity,
                   p.unit AS active_product_unit, p.cost_price AS current_cost_price
            FROM movements m
            LEFT JOIN products p ON p.id = m.product_id AND p.user_id = m.user_id
            WHERE m.id = %s AND m.user_id = %s
            """,
            (movement_id, g.user["id"]),
        ).fetchone()
    if movement is None:
        abort(404)

    has_active_product = movement["active_product_id"] is not None
    if request.method == "GET":
        return render_template(
            "movement_edit.html",
            movement=movement,
            has_active_product=has_active_product,
            payment_methods=PAYMENT_METHODS,
        )

    with database_connection() as conn:
        movement = conn.execute(
            "SELECT * FROM movements WHERE id = %s AND user_id = %s FOR UPDATE",
            (movement_id, g.user["id"]),
        ).fetchone()
        if movement is None:
            abort(404)

        product = None
        if movement["product_id"] is not None:
            product = conn.execute(
                """
                SELECT id, quantity, unit, cost_price, sale_price
                FROM products
                WHERE id = %s AND user_id = %s
                FOR UPDATE
                """,
                (movement["product_id"], g.user["id"]),
            ).fetchone()

        kind = movement["kind"]
        quantity_raw = (
            request.form.get("quantity", str(movement["quantity"]))
            if product
            else str(movement["quantity"])
        )
        note = request.form.get("note", "").strip()
        payment_method = (
            request.form.get("payment_method", "") if kind == "OUT" else None
        )
        discount_type = request.form.get("discount_type", movement["discount_type"])
        discount_value_raw = request.form.get(
            "discount_value", str(movement["discount_value"])
        ).strip()
        try:
            quantity = int(quantity_raw)
        except ValueError:
            quantity = 0

        try:
            if kind == "OUT":
                cost_unit_price = normalize_price(
                    Decimal(
                        request.form.get("cost_unit_price", "")
                        .strip()
                        .replace(",", ".")
                    )
                )
                sale_price = movement["sale_unit_price"]
                if sale_price is None and product is not None:
                    sale_price = product["sale_price"]
                sale_unit_price = (
                    normalize_price(sale_price) if sale_price is not None else None
                )
            else:
                cost_unit_price = None
                sale_unit_price = None
        except InvalidOperation:
            cost_unit_price = None
            sale_unit_price = None

        discount_value = Decimal("0")
        discount_amount = Decimal("0")
        discount_error = None
        if (
            kind == "OUT"
            and sale_unit_price is not None
            and sale_unit_price.is_finite()
            and quantity > 0
        ):
            discount_value, discount_amount, discount_error = calculate_discount(
                discount_type,
                discount_value_raw,
                sale_unit_price * quantity,
            )

        validation_error = None
        if kind not in ("IN", "OUT"):
            validation_error = "Selecione entrada ou saída."
        elif quantity <= 0:
            validation_error = (
                "A quantidade precisa ser um número inteiro maior que zero."
            )
        elif quantity > MAX_QUANTITY:
            validation_error = "A quantidade excede o limite permitido."
        elif len(note) > 240:
            validation_error = "A observação pode ter até 240 caracteres."
        elif kind == "OUT" and payment_method not in PAYMENT_METHODS:
            validation_error = "Selecione um método de pagamento válido."
        elif kind == "OUT" and discount_error:
            validation_error = discount_error
        elif kind == "OUT" and (cost_unit_price is None or sale_unit_price is None):
            validation_error = (
                "Informe custos e preço de venda válidos dentro do limite permitido."
            )

        # Reverte o efeito antigo da movimentação e aplica o efeito editado ao saldo.
        new_stock_quantity = None
        if validation_error is None and product:
            previous_effect = (
                movement["quantity"]
                if movement["kind"] == "IN"
                else -movement["quantity"]
            )
            new_effect = quantity if kind == "IN" else -quantity
            new_stock_quantity = product["quantity"] - previous_effect + new_effect
            if new_stock_quantity < 0:
                validation_error = "Estoque insuficiente para completar o pedido."
            elif new_stock_quantity > MAX_QUANTITY:
                validation_error = (
                    "O ajuste excederia o limite permitido para o saldo do estoque."
                )

        if validation_error:
            flash(validation_error, "error")
            return render_template(
                "movement_edit.html",
                movement=movement,
                has_active_product=product is not None,
                payment_methods=PAYMENT_METHODS,
            )

        conn.execute(
            """
            UPDATE movements
            SET kind = %s, quantity = %s, note = %s,
                cost_unit_price = %s, sale_unit_price = %s, payment_method = %s,
                discount_type = %s, discount_value = %s, discount_amount = %s
            WHERE id = %s AND user_id = %s
            """,
            (
                kind,
                quantity,
                note,
                cost_unit_price,
                sale_unit_price,
                payment_method,
                discount_type if kind == "OUT" else "AMOUNT",
                discount_value,
                discount_amount,
                movement_id,
                g.user["id"],
            ),
        )
        if product and new_stock_quantity is not None:
            conn.execute(
                """
                UPDATE products SET quantity = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (new_stock_quantity, product["id"], g.user["id"]),
            )

    flash(
        "Movimentação atualizada. Os valores do painel foram recalculados.", "success"
    )
    return redirect(url_for("sales" if movement["kind"] == "OUT" else "movements"))


@app.route("/movimentacoes/<int:movement_id>/excluir", methods=["POST"])
@login_required
def delete_movement(movement_id):
    """Remove uma movimentação e desfaz seu efeito sobre o estoque atual."""
    with database_connection() as conn:
        movement = conn.execute(
            "SELECT * FROM movements WHERE id = %s AND user_id = %s FOR UPDATE",
            (movement_id, g.user["id"]),
        ).fetchone()
        if movement is None:
            abort(404)

        if movement["product_id"] is not None:
            product = conn.execute(
                """
                SELECT id, quantity
                FROM products
                WHERE id = %s AND user_id = %s
                FOR UPDATE
                """,
                (movement["product_id"], g.user["id"]),
            ).fetchone()
            if product:
                adjustment = (
                    -movement["quantity"]
                    if movement["kind"] == "IN"
                    else movement["quantity"]
                )
                conn.execute(
                    """
                    UPDATE products SET quantity = quantity + %s, updated_at = NOW()
                    WHERE id = %s AND user_id = %s
                    """,
                    (adjustment, product["id"], g.user["id"]),
                )

        conn.execute(
            "DELETE FROM movements WHERE id = %s AND user_id = %s",
            (movement_id, g.user["id"]),
        )

    flash("Movimentação excluída e valores do painel atualizados.", "success")
    return redirect(url_for("sales" if movement["kind"] == "OUT" else "movements"))

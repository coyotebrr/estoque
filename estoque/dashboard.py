"""Consulta os indicadores e listas exibidos no painel inicial."""

from flask import g, render_template

from . import app
from .database import database_connection
from .security import login_required


@app.route("/painel")
@login_required
def dashboard():
    """Carrega totais do estoque, vendas, itens críticos e movimentações recentes."""
    with database_connection() as conn:
        summary = conn.execute(
            """
            SELECT
                COUNT(*) AS product_count,
                COALESCE(SUM(quantity), 0) AS unit_count,
                COUNT(*) FILTER (WHERE quantity <= min_stock) AS low_stock_count,
                COALESCE(SUM(quantity * cost_price), 0) AS stock_value
            FROM products
            WHERE user_id = %s
            """,
            (g.user["id"],),
        ).fetchone()
        sales_summary = conn.execute(
            """
            SELECT
                COALESCE(SUM(quantity * cost_unit_price), 0) AS invested_value,
                COALESCE(SUM(quantity * sale_unit_price - discount_amount), 0) AS sales_value,
                COALESCE(SUM(quantity * sale_unit_price - discount_amount - quantity * cost_unit_price), 0) AS profit,
                COUNT(*) FILTER (
                    WHERE sale_unit_price IS NULL OR cost_unit_price IS NULL
                ) AS unpriced_out_count
            FROM movements
            WHERE user_id = %s AND kind = 'OUT'
            """,
            (g.user["id"],),
        ).fetchone()
        low_stock = conn.execute(
            """
            SELECT id, name, quantity, min_stock, unit
            FROM products
            WHERE user_id = %s AND quantity <= min_stock
            ORDER BY quantity ASC, name ASC
            LIMIT 5
            """,
            (g.user["id"],),
        ).fetchall()
        recent_movements = conn.execute(
            """
            SELECT m.id, m.kind, m.quantity, m.note, m.created_at,
                   m.sale_unit_price, m.cost_unit_price,
                   COALESCE(m.product_name_snapshot, p.name) AS product_name,
                   COALESCE(m.product_unit_snapshot, p.unit) AS unit
            FROM movements m
            LEFT JOIN products p ON p.id = m.product_id AND p.user_id = m.user_id
            WHERE m.user_id = %s
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT 6
            """,
            (g.user["id"],),
        ).fetchall()
    return render_template(
        "dashboard.html",
        summary=summary,
        sales_summary=sales_summary,
        low_stock=low_stock,
        recent_movements=recent_movements,
    )

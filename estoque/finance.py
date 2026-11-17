"""Relatórios financeiros agregados por período e método de pagamento."""

from flask import g, request, render_template

from . import app
from .constants import PAYMENT_METHODS
from .database import database_connection
from .security import login_required


@app.route("/financeiro")
@login_required
def finance():
    """Calcula totais, resumo por pagamento e histórico financeiro paginado."""
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = 50
    offset = (page - 1) * page_size
    with database_connection() as conn:
        summary = conn.execute(
            """
            SELECT
                COALESCE(SUM(quantity * cost_unit_price), 0) AS invested_value,
                COALESCE(SUM(quantity * sale_unit_price), 0) AS gross_sales_value,
                COALESCE(SUM(discount_amount), 0) AS discount_value,
                COALESCE(SUM(quantity * sale_unit_price - discount_amount), 0) AS sales_value,
                COALESCE(SUM(quantity * sale_unit_price - discount_amount - quantity * cost_unit_price), 0) AS profit,
                COUNT(*) FILTER (
                    WHERE sale_unit_price IS NULL OR cost_unit_price IS NULL
                ) AS unpriced_out_count,
                COUNT(*) AS sale_count
            FROM movements
            WHERE user_id = %s AND kind = 'OUT'
            """,
            (g.user["id"],),
        ).fetchone()
        total_count = summary["sale_count"]
        payment_rows = conn.execute(
            """
            SELECT payment_method,
                   COUNT(*) AS sale_count,
                   COALESCE(SUM(quantity * cost_unit_price), 0) AS invested_value,
                   COALESCE(SUM(quantity * sale_unit_price), 0) AS gross_sales_value,
                   COALESCE(SUM(discount_amount), 0) AS discount_value,
                   COALESCE(SUM(quantity * sale_unit_price - discount_amount), 0) AS sales_value,
                   COALESCE(SUM(quantity * sale_unit_price - discount_amount - quantity * cost_unit_price), 0) AS profit
            FROM movements
            WHERE user_id = %s AND kind = 'OUT'
            GROUP BY payment_method
            """,
            (g.user["id"],),
        ).fetchall()
        payments_by_method = {row["payment_method"]: row for row in payment_rows}
        # Inclui também métodos sem vendas no período para manter todos visíveis.
        payment_summary = [
            {
                "method": method,
                "sale_count": (
                    payments_by_method[method]["sale_count"]
                    if method in payments_by_method
                    else 0
                ),
                "invested_value": (
                    payments_by_method[method]["invested_value"]
                    if method in payments_by_method
                    else 0
                ),
                "gross_sales_value": (
                    payments_by_method[method]["gross_sales_value"]
                    if method in payments_by_method
                    else 0
                ),
                "discount_value": (
                    payments_by_method[method]["discount_value"]
                    if method in payments_by_method
                    else 0
                ),
                "sales_value": (
                    payments_by_method[method]["sales_value"]
                    if method in payments_by_method
                    else 0
                ),
                "profit": (
                    payments_by_method[method]["profit"]
                    if method in payments_by_method
                    else 0
                ),
            }
            for method in PAYMENT_METHODS
        ]
        if None in payments_by_method:
            payment_summary.append(
                {
                    "method": "Não informado",
                    "sale_count": payments_by_method[None]["sale_count"],
                    "invested_value": payments_by_method[None]["invested_value"],
                    "gross_sales_value": payments_by_method[None]["gross_sales_value"],
                    "discount_value": payments_by_method[None]["discount_value"],
                    "sales_value": payments_by_method[None]["sales_value"],
                    "profit": payments_by_method[None]["profit"],
                }
            )
        rows = conn.execute(
            """
            SELECT m.id, m.quantity, m.note, m.created_at,
                   m.cost_unit_price, m.sale_unit_price, m.payment_method,
                   m.discount_type, m.discount_value, m.discount_amount,
                   m.quantity * m.sale_unit_price AS gross_sales_value,
                   m.quantity * m.sale_unit_price - m.discount_amount AS sales_value,
                   m.quantity * m.sale_unit_price - m.discount_amount
                       - m.quantity * m.cost_unit_price AS profit,
                   COALESCE(m.product_name_snapshot, p.name) AS product_name,
                   COALESCE(m.product_unit_snapshot, p.unit) AS unit
            FROM movements m
            LEFT JOIN products p ON p.id = m.product_id AND p.user_id = m.user_id
            WHERE m.user_id = %s AND m.kind = 'OUT'
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT %s OFFSET %s
            """,
            (g.user["id"], page_size, offset),
        ).fetchall()
    total_pages = max((total_count + page_size - 1) // page_size, 1)
    return render_template(
        "finance.html",
        summary=summary,
        payment_summary=payment_summary,
        movements=rows,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )

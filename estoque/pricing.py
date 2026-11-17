"""Validação de preços e cálculo de descontos para operações financeiras."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .constants import CENT, MAX_PRICE

MAX_DISCOUNT_AMOUNT = Decimal("99999999999999999999.99")


def normalize_price(value: Decimal) -> Decimal | None:
    """Valida um preço e arredonda valores monetários para centavos."""
    if not value.is_finite() or value < 0 or value > MAX_PRICE:
        return None
    try:
        return value.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def calculate_discount(discount_type, discount_value_raw, gross_total):
    """Valida desconto percentual ou fixo e retorna valor informado e abatimento."""
    try:
        discount_value = Decimal(discount_value_raw.replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None, None, "Informe um desconto válido."

    if not discount_value.is_finite() or discount_value < 0:
        return None, None, "Informe um desconto válido e não negativo."
    if discount_value > MAX_PRICE:
        return None, None, "O desconto excede o limite permitido."
    try:
        discount_value = discount_value.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None, None, "Informe um desconto válido."

    if discount_type == "PERCENT":
        if discount_value > 100:
            return None, None, "O desconto percentual não pode ultrapassar 100%."
        discount_amount = (gross_total * discount_value / Decimal("100")).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
    elif discount_type == "AMOUNT":
        discount_amount = discount_value.quantize(CENT, rounding=ROUND_HALF_UP)
    else:
        return None, None, "Selecione um tipo de desconto válido."

    if discount_amount > MAX_DISCOUNT_AMOUNT:
        return None, None, "O desconto excede o limite permitido."
    if discount_amount > gross_total:
        return None, None, "O desconto não pode ser maior que o valor da venda."

    return discount_value, discount_amount, None

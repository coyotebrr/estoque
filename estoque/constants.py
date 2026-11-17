"""Valores e limites compartilhados entre os módulos da aplicação."""

from decimal import Decimal

# Métodos aceitos ao registrar ou editar uma venda.
PAYMENT_METHODS = ("PIX", "DEBITO", "CREDITO", "DINHEIRO")
# Limites usados para validar quantidades e valores monetários.
MAX_QUANTITY = 2147483647
MAX_PRICE = Decimal("9999999999.99")
# Precisão monetária de centavos.
CENT = Decimal("0.01")

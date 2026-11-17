"""Conexão PostgreSQL e criação/migração do esquema da aplicação."""

import os

import psycopg
from psycopg.rows import dict_row


def database_connection():
    """Abre uma conexão PostgreSQL com resultados acessíveis pelo nome da coluna."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "A variável DATABASE_URL não foi definida. Consulte o README.md para configurar o PostgreSQL."
        )
    return psycopg.connect(database_url, row_factory=dict_row)


def init_db():
    """Cria tabelas, índices e atualiza estruturas para bancos já existentes."""
    statements = [
        # Define usuários e produtos, incluindo os preços e regras atuais de estoque.
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            email VARCHAR(254) NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_idx ON users (LOWER(email))",
        """
        CREATE TABLE IF NOT EXISTS products (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(160) NOT NULL,
            sku VARCHAR(80) NOT NULL DEFAULT '',
            category VARCHAR(100) NOT NULL DEFAULT '',
            unit VARCHAR(30) NOT NULL DEFAULT 'UN',
            quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
            min_stock INTEGER NOT NULL DEFAULT 0 CHECK (min_stock >= 0),
            cost_price NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (cost_price >= 0),
            sale_price NUMERIC(12, 2) CHECK (sale_price >= 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'products'
                  AND column_name = 'price'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'products'
                  AND column_name = 'cost_price'
            ) THEN
                ALTER TABLE products RENAME COLUMN price TO cost_price;
            END IF;
        END;
        $$
        """,
        """
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS cost_price NUMERIC(12, 2) NOT NULL DEFAULT 0
        CHECK (cost_price >= 0)
        """,
        """
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS sale_price NUMERIC(12, 2)
        CHECK (sale_price >= 0)
        """,
        "UPDATE products SET unit = UPPER(unit) WHERE unit <> UPPER(unit)",
        "ALTER TABLE products ALTER COLUMN unit SET DEFAULT 'UN'",
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'products'::regclass
                  AND conname = 'products_unit_uppercase_check'
            ) THEN
                ALTER TABLE products
                ADD CONSTRAINT products_unit_uppercase_check CHECK (unit = UPPER(unit));
            END IF;
        END;
        $$
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS products_user_sku_lower_idx
        ON products (user_id, LOWER(sku)) WHERE sku <> ''
        """,
        "CREATE INDEX IF NOT EXISTS products_user_name_idx ON products (user_id, name)",
        """
        CREATE TABLE IF NOT EXISTS movements (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
            kind VARCHAR(3) NOT NULL CHECK (kind IN ('IN', 'OUT')),
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            note VARCHAR(240) NOT NULL DEFAULT '',
            cost_unit_price NUMERIC(12, 2) CHECK (cost_unit_price >= 0),
            sale_unit_price NUMERIC(12, 2) CHECK (sale_unit_price >= 0),
            payment_method VARCHAR(10) CHECK (
                payment_method IS NULL OR payment_method IN ('PIX', 'DEBITO', 'CREDITO', 'DINHEIRO')
            ),
            discount_type VARCHAR(10) NOT NULL DEFAULT 'AMOUNT'
                CHECK (discount_type IN ('PERCENT', 'AMOUNT')),
            discount_value NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (discount_value >= 0),
            discount_amount NUMERIC(22, 2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
            product_name_snapshot VARCHAR(160),
            product_unit_snapshot VARCHAR(30),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        ALTER TABLE movements
        ADD COLUMN IF NOT EXISTS cost_unit_price NUMERIC(12, 2)
        CHECK (cost_unit_price >= 0)
        """,
        """
        ALTER TABLE movements
        ADD COLUMN IF NOT EXISTS sale_unit_price NUMERIC(12, 2)
        CHECK (sale_unit_price >= 0)
        """,
        """
        ALTER TABLE movements
        ADD COLUMN IF NOT EXISTS payment_method VARCHAR(10)
        CHECK (payment_method IS NULL OR payment_method IN ('PIX', 'DEBITO', 'CREDITO', 'DINHEIRO'))
        """,
        """
        ALTER TABLE movements
        ADD COLUMN IF NOT EXISTS discount_type VARCHAR(10) NOT NULL DEFAULT 'AMOUNT'
        CHECK (discount_type IN ('PERCENT', 'AMOUNT'))
        """,
        """
        ALTER TABLE movements
        ADD COLUMN IF NOT EXISTS discount_value NUMERIC(12, 2) NOT NULL DEFAULT 0
        CHECK (discount_value >= 0)
        """,
        """
        ALTER TABLE movements
        ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(22, 2) NOT NULL DEFAULT 0
        CHECK (discount_amount >= 0)
        """,
        "ALTER TABLE movements ALTER COLUMN discount_amount TYPE NUMERIC(22, 2)",
        """
        ALTER TABLE movements
        ADD COLUMN IF NOT EXISTS product_name_snapshot VARCHAR(160)
        """,
        """
        ALTER TABLE movements
        ADD COLUMN IF NOT EXISTS product_unit_snapshot VARCHAR(30)
        """,
        """
        UPDATE movements AS m
        SET product_name_snapshot = p.name,
            product_unit_snapshot = p.unit
        FROM products AS p
        WHERE p.id = m.product_id
          AND (m.product_name_snapshot IS NULL OR m.product_unit_snapshot IS NULL)
        """,
        """
        UPDATE movements
        SET product_unit_snapshot = UPPER(product_unit_snapshot)
        WHERE product_unit_snapshot <> UPPER(product_unit_snapshot)
        """,
        """
        ALTER TABLE movements
        ALTER COLUMN product_name_snapshot SET NOT NULL,
        ALTER COLUMN product_unit_snapshot SET NOT NULL
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'movements'::regclass
                  AND conname = 'movements_product_unit_uppercase_check'
            ) THEN
                ALTER TABLE movements
                ADD CONSTRAINT movements_product_unit_uppercase_check
                CHECK (product_unit_snapshot = UPPER(product_unit_snapshot));
            END IF;
        END;
        $$
        """,
        """
        DO $$
        DECLARE
            fk_constraint RECORD;
        BEGIN
            FOR fk_constraint IN
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'movements'::regclass
                  AND confrelid = 'products'::regclass
                  AND contype = 'f'
                  AND confdeltype <> 'n'
            LOOP
                EXECUTE format(
                    'ALTER TABLE movements DROP CONSTRAINT %I',
                    fk_constraint.conname
                );
            END LOOP;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'movements'::regclass
                  AND confrelid = 'products'::regclass
                  AND contype = 'f'
                  AND confdeltype = 'n'
            ) THEN
                ALTER TABLE movements
                ADD CONSTRAINT movements_product_id_fkey
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL;
            END IF;
        END;
        $$
        """,
        "ALTER TABLE movements ALTER COLUMN product_id DROP NOT NULL",
        "CREATE INDEX IF NOT EXISTS movements_user_created_idx ON movements (user_id, created_at DESC)",
    ]
    # Executa cada criação ou migração dentro do contexto transacional da conexão.
    with database_connection() as conn:
        for statement in statements:
            conn.execute(statement)

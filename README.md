# Estoque Fácil

Sistema web de controle de estoque feito em Python, Flask e PostgreSQL. Cada usuário tem sua própria conta e só pode acessar seus produtos e movimentações.

## Requisitos

- Python 3.10 ou superior
- PostgreSQL instalado e em execução

## Preparar o PostgreSQL

No PostgreSQL, crie um banco de dados e um usuário para a aplicação. Por exemplo, no `psql`:

```sql
CREATE USER estoque_app WITH PASSWORD 'escolha-uma-senha-forte';
CREATE DATABASE estoque_db OWNER estoque_app;
```

Com o banco criado, você pode criar as tabelas manualmente executando o arquivo `schema.sql`:

```powershell
psql -U estoque_app -d estoque_db -f schema.sql
```

Essa etapa é opcional: a primeira execução da aplicação também cria as tabelas automaticamente.

## Executar no Windows

Abra o PowerShell nesta pasta e execute:

O código Python está organizado no pacote `estoque/`, com módulos separados para banco de dados (`database.py`), autenticação (`auth.py`), painel (`dashboard.py`), produtos e estoque (`products.py`), movimentações (`movements.py`), vendas (`sales.py`) e financeiro (`finance.py`). Regras compartilhadas ficam em `constants.py`, e cálculos e validações monetárias em `pricing.py`. O `app.py` na raiz mantém o comando de inicialização. Os templates ficam em `templates/`; os estilos são separados por função em `static/css/` e carregados conforme a página, enquanto `static/style.css` mantém um ponto de entrada compatível.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "postgresql://estoque_app:escolha-uma-senha-forte@localhost:5432/estoque_db"
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python app.py
```

Se o PowerShell bloquear a ativação do ambiente virtual, você também pode instalar e executar sem ativá-lo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Nesse caso, defina `DATABASE_URL` e `SECRET_KEY` na mesma janela do PowerShell antes de iniciar a aplicação. A primeira execução cria as tabelas automaticamente.

Abra [http://127.0.0.1:5000](http://127.0.0.1:5000) no navegador e crie sua conta.

## Funcionalidades

- Registro de usuário e login com senha armazenada em formato protegido.
- Painel com quantidade de produtos, investimento em estoque, lucro das saídas e alertas de estoque baixo.
- Cadastro, edição, busca e organização de produtos por usuário, incluindo custo e preço de venda unitários.
- Unidades de medida salvas e exibidas sempre em letras maiúsculas.
- Área de estoque para consulta e manutenção dos produtos, com histórico de entradas e saídas na área de movimentações.
- Área de vendas para registrar saídas usando automaticamente o preço unitário cadastrado no produto, método de pagamento (PIX, débito, crédito ou dinheiro) e descontos em percentual ou valor; o saldo é atualizado automaticamente.
- Histórico e edição das movimentações e vendas, com atualização automática do saldo e dos valores financeiros.
- Edição e exclusão de movimentações, com ajuste automático do estoque e recálculo dos valores do painel.
- Área financeira com totais e detalhamento paginado do faturamento bruto e líquido, descontos, vendas por método de pagamento, custos e lucros.
- Cálculo do lucro por saída usando o custo unitário cadastrado no produto e o preço de venda informado, descontando os abatimentos aplicados.
- Exclusão de produtos sem apagar o histórico de movimentações associado.
- Bloqueio de saídas acima do estoque disponível.

O aplicativo adiciona automaticamente as novas colunas ao banco existente; o preço unitário antigo dos produtos é preservado e passa a ser tratado como custo de aquisição. Saídas registradas antes de informar o preço de venda não entram no cálculo do lucro.

Para hospedar a aplicação publicamente, configure uma chave `SECRET_KEY` estável, use HTTPS (`SESSION_COOKIE_SECURE=1`) e execute Flask atrás de um servidor WSGI apropriado.

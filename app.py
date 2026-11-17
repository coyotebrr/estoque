# Permite ler configurações do ambiente, como a porta do servidor.
import os

# Importa a aplicação Flask e a função que prepara o banco de dados.
from estoque import app, init_db

# Executa este bloco apenas quando o arquivo é iniciado diretamente.
if __name__ == "__main__":
    # Cria ou atualiza as estruturas necessárias no banco de dados.
    init_db()
    # Inicia o servidor local; usa a porta definida em PORT ou 5000 por padrão.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))

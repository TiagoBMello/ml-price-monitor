import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd
from collector import Listing

# Caminho do banco de dados, relativo à raiz do projeto
_DB_PATH = Path(__file__).parent.parent / "data" / "prices.db"


def criar_banco() -> None:
    """Cria o diretório data/ e a tabela 'precos' caso ainda não existam."""
    # Garante que a pasta data/ existe antes de criar o arquivo .db
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS precos (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                produto      TEXT    NOT NULL,  -- termo buscado pelo usuário
                preco        REAL    NOT NULL,
                vendedor     TEXT,
                reputacao    TEXT,
                data_coleta  TEXT    NOT NULL   -- ISO-8601: 'YYYY-MM-DD HH:MM:SS'
            )
            """
        )
        conn.commit()


def salvar_precos(listings: list[Listing], produto_buscado: str) -> int:
    """Persiste uma lista de Listings no banco e retorna a quantidade inserida.

    Args:
        listings: resultados retornados por collector.search().
        produto_buscado: termo de busca original, salvo na coluna 'produto'
                         para facilitar consultas futuras.
    """
    if not listings:
        return 0

    # Timestamp único para toda a coleta — permite agrupar registros de uma mesma rodada
    data_coleta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Monta os registros como tuplas para inserção em lote (mais eficiente que um INSERT por vez)
    registros = [
        (
            produto_buscado,
            listing.price,
            listing.seller_name,
            listing.seller_reputation,
            data_coleta,
        )
        for listing in listings
    ]

    with sqlite3.connect(_DB_PATH) as conn:
        conn.executemany(
            "INSERT INTO precos (produto, preco, vendedor, reputacao, data_coleta) "
            "VALUES (?, ?, ?, ?, ?)",
            registros,
        )
        conn.commit()

    return len(registros)


def buscar_historico(produto: str) -> pd.DataFrame:
    """Retorna o histórico de preços de um produto como DataFrame.

    A busca é case-insensitive e usa LIKE para aceitar correspondências parciais,
    ex.: buscar_historico("note") encontra registros com produto="notebook".

    Args:
        produto: termo de busca (parcial ou completo).

    Returns:
        DataFrame com colunas: id, produto, preco, vendedor, reputacao, data_coleta.
        Retorna DataFrame vazio se nenhum registro for encontrado.
    """
    with sqlite3.connect(_DB_PATH) as conn:
        # LOWER + LIKE garante correspondência sem diferenciar maiúsculas/minúsculas
        df = pd.read_sql_query(
            "SELECT * FROM precos WHERE LOWER(produto) LIKE LOWER(?)",
            conn,
            params=(f"%{produto}%",),
        )

    # Converte a coluna de data para datetime para facilitar análises com pandas
    if not df.empty:
        df["data_coleta"] = pd.to_datetime(df["data_coleta"])

    return df


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from collector import search

    print("1. Criando banco de dados...")
    criar_banco()
    print(f"   Banco criado em: {_DB_PATH}\n")

    print("2. Coletando preços de 'notebook' no Mercado Livre...")
    listings = search("notebook", max_results=5)
    print(f"   {len(listings)} resultados coletados.\n")

    print("3. Salvando no banco...")
    inseridos = salvar_precos(listings, produto_buscado="notebook")
    print(f"   {inseridos} registros inseridos.\n")

    print("4. Buscando histórico de 'notebook'...")
    df = buscar_historico("notebook")
    print(df.to_string(index=False))

"""
sync_indices.py — Sincroniza índices monetários do BCB/SGS para PostgreSQL (schema aux)

Uso:
    python sync_indices.py              # incremental: só meses novos
    python sync_indices.py --inicial    # carga histórica completa (primeira execução)
"""

import sys
import logging
import argparse
import configparser
from datetime import date, datetime
from pathlib import Path

import psycopg2
import psycopg2.extras

from main import buscar_serie

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
LOG_DIR    = SCRIPT_DIR / ".logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(
            LOG_DIR / f"sync_indices_{date.today().strftime('%Y%m%d')}.log",
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Catálogo — mesmos índices do main.py, com data de início histórico
# ---------------------------------------------------------------------------

INDICES_SYNC = [
    {"nome": "IGP-M",   "codigo": 189,  "data_ini": date(1944,  1, 1)},
    {"nome": "IGP-DI",  "codigo": 190,  "data_ini": date(1944,  1, 1)},
    {"nome": "IPCA",    "codigo": 433,  "data_ini": date(1980,  1, 1)},
    {"nome": "INPC",    "codigo": 188,  "data_ini": date(1979, 12, 1)},
    {"nome": "INCC-DI", "codigo": 192,  "data_ini": date(1944,  1, 1)},
    {"nome": "CDI",     "codigo": 4391, "data_ini": date(1986,  1, 1)},
    {"nome": "SELIC",   "codigo": 4390, "data_ini": date(1986,  1, 1)},
    # TR (226) e Poupanca (195) são séries diárias na API BCB — fora do escopo
]

# ---------------------------------------------------------------------------
# Conexão PostgreSQL
# ---------------------------------------------------------------------------

def _carregar_config() -> dict:
    cfg_path = SCRIPT_DIR / "db_config.ini"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {cfg_path}\n"
            "Copie db_config.ini.exemplo para db_config.ini e preencha as credenciais."
        )
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path, encoding="utf-8")
    return dict(cfg["postgresql"])


def conectar() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(**_carregar_config())
    conn.autocommit = False
    return conn

# ---------------------------------------------------------------------------
# Operações no banco
# ---------------------------------------------------------------------------

def _ultimo_mes_gravado(conn, nome: str) -> date | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT MAX(competencia) FROM aux.indices_monetarios WHERE indice = %s",
            (nome,),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else None


def _proximo_mes(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def _parse_data_bcb(raw: str) -> date:
    """Aceita DD/MM/AAAA ou MM/AAAA — ambos retornados pela API conforme a série."""
    raw = raw.strip()
    if len(raw) == 7:   # MM/AAAA
        return datetime.strptime(raw, "%m/%Y").date().replace(day=1)
    return datetime.strptime(raw, "%d/%m/%Y").date().replace(day=1)


def _inserir(conn, nome: str, serie: list[dict]) -> int:
    registros = []
    for ponto in serie:
        try:
            competencia = _parse_data_bcb(ponto["data"])
            taxa        = float(ponto["valor"])
            registros.append((nome, competencia, taxa))
        except Exception as e:
            log.warning(f"  [{nome}] Ponto ignorado {ponto}: {e}")

    if not registros:
        return 0

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO aux.indices_monetarios (indice, competencia, taxa)
            VALUES %s
            ON CONFLICT (indice, competencia) DO NOTHING
            """,
            registros,
        )
    conn.commit()
    return len(registros)

# ---------------------------------------------------------------------------
# Sincronização por índice
# ---------------------------------------------------------------------------

def sincronizar_indice(conn, idx: dict, carga_inicial: bool) -> bool:
    nome   = idx["nome"]
    codigo = idx["codigo"]

    if carga_inicial:
        data_ini = idx["data_ini"]
        log.info(f"[{nome}] Carga inicial desde {data_ini.strftime('%m/%Y')} ...")
    else:
        ultimo = _ultimo_mes_gravado(conn, nome)
        if ultimo is None:
            data_ini = idx["data_ini"]
            log.info(f"[{nome}] Sem dados no banco — iniciando desde {data_ini.strftime('%m/%Y')} ...")
        else:
            data_ini = _proximo_mes(ultimo)
            log.info(f"[{nome}] Incremental a partir de {data_ini.strftime('%m/%Y')} ...")

    data_fim = date.today()

    if data_ini > data_fim:
        log.info(f"[{nome}] Já está atualizado. Nenhuma ação necessária.")
        return True

    try:
        serie = buscar_serie(codigo, data_ini, data_fim)
    except RuntimeError as e:
        log.error(f"[{nome}] Falha na API BCB: {e}")
        return False

    if not serie:
        log.warning(f"[{nome}] API não retornou dados para o período solicitado.")
        return True

    n = _inserir(conn, nome, serie)
    log.info(f"[{nome}] {n} registro(s) inserido(s).")
    return True

# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza índices BCB/SGS → PostgreSQL (schema aux)"
    )
    parser.add_argument(
        "--inicial",
        action="store_true",
        help="Carga histórica completa. Use apenas na primeira execução.",
    )
    args = parser.parse_args()

    modo = "INICIAL (histórico completo)" if args.inicial else "INCREMENTAL (novos meses)"
    log.info("=" * 60)
    log.info(f"Sync BCB → PostgreSQL  |  Modo: {modo}")
    log.info("=" * 60)

    try:
        conn = conectar()
        log.info("Conexão com PostgreSQL estabelecida.")
    except FileNotFoundError as e:
        log.critical(str(e))
        sys.exit(1)
    except psycopg2.Error as e:
        log.critical(f"Falha na conexão com PostgreSQL: {e}")
        sys.exit(1)

    falhas = []
    for idx in INDICES_SYNC:
        ok = sincronizar_indice(conn, idx, carga_inicial=args.inicial)
        if not ok:
            falhas.append(idx["nome"])

    conn.close()

    log.info("=" * 60)
    if falhas:
        log.error(f"Sync concluído com falha(s) em: {', '.join(falhas)}")
        sys.exit(1)

    log.info("Sync concluído com sucesso.")
    sys.exit(0)


if __name__ == "__main__":
    main()

"""
Calculadora de Correção Monetária — BCB/SGS
Consulta índices oficiais do Banco Central do Brasil e calcula
o valor corrigido de um montante em um determinado período.
"""
import io
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

import requests
from colorama import Fore, Style, init

APP_NOME   = "Calculadora de Correção Monetária"
APP_VERSAO = "V01.00"
BCB_URL    = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    "?formato=json&dataInicial={ini}&dataFinal={fim}"
)

# ---------------------------------------------------------------------------
# Catálogo de índices (código SGS do Banco Central)
# ---------------------------------------------------------------------------

INDICES = [
    {"nome": "IGP-M",    "codigo": 189,  "desc": "Índice Geral de Preços do Mercado (FGV)"},
    {"nome": "IGP-DI",   "codigo": 190,  "desc": "Índice Geral de Preços — Disp. Interna (FGV)"},
    {"nome": "IPCA",     "codigo": 433,  "desc": "Índice de Preços ao Consumidor Amplo (IBGE)"},
    {"nome": "INPC",     "codigo": 188,  "desc": "Índice Nacional de Preços ao Consumidor (IBGE)"},
    {"nome": "INCC-DI",  "codigo": 192,  "desc": "Índice Nacional do Custo da Construção — DI (FGV)"},
    {"nome": "CDI",      "codigo": 4391, "desc": "Taxa CDI acumulada no mês"},
    {"nome": "SELIC",    "codigo": 4390, "desc": "Taxa SELIC over acumulada no mês"},
    {"nome": "TR",       "codigo": 226,  "desc": "Taxa Referencial mensal"},
    {"nome": "Poupança", "codigo": 195,  "desc": "Rendimento da caderneta de poupança (mensal)"},
]

# ---------------------------------------------------------------------------
# Console
# ---------------------------------------------------------------------------

def _sep(char="─", n=62):
    return char * n

def cabecalho(msg: str) -> None:
    print(f"\n{Fore.CYAN}{_sep()}")
    print(f"  {msg}")
    print(f"{_sep()}{Style.RESET_ALL}")

def ok(msg: str) -> None:
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL}  {msg}")

def erro(msg: str) -> None:
    print(f"  {Fore.RED}✗  {msg}{Style.RESET_ALL}")

def aviso(msg: str) -> None:
    print(f"  {Fore.YELLOW}!  {msg}{Style.RESET_ALL}")

def entrada(prompt: str, default: str = "") -> str:
    sufixo = f" [{default}]" if default else ""
    resp = input(f"  {prompt}{sufixo}: ").strip()
    return resp if resp else default

# ---------------------------------------------------------------------------
# Parsing e formatação
# ---------------------------------------------------------------------------

def parse_mes_ano(s: str) -> date:
    """Aceita MM/AAAA ou MM/AA."""
    for fmt in ("%m/%Y", "%m/%y"):
        try:
            d = datetime.strptime(s.strip(), fmt)
            return date(d.year, d.month, 1)
        except ValueError:
            pass
    raise ValueError(f"Formato inválido: '{s}'. Use MM/AAAA.")

def parse_valor(s: str) -> Decimal:
    """Aceita 1.234,56 ou 1234.56 ou 1234,56."""
    s = s.strip().replace("R$", "").replace(" ", "")
    # detectar separador decimal: se vírgula vier depois de ponto → formato BR
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = Decimal(s)
        if v <= 0:
            raise ValueError("O valor deve ser positivo.")
        return v
    except Exception:
        raise ValueError(f"Valor inválido: '{s}'.")

def fmt_brl(v: Decimal) -> str:
    s = f"{v:,.2f}"                    # 1,234.56
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(v: Decimal) -> str:
    return f"{v:.4f}%".replace(".", ",")

# ---------------------------------------------------------------------------
# BCB / SGS
# ---------------------------------------------------------------------------

def buscar_serie(codigo: int, data_ini: date, data_fim: date) -> list[dict]:
    url = BCB_URL.format(
        codigo=codigo,
        ini=data_ini.strftime("%d/%m/%Y"),
        fim=data_fim.strftime("%d/%m/%Y"),
    )
    # Tenta com verificação SSL; se falhar (firewall corporativo), tenta sem
    for verify in (True, False):
        try:
            if not verify:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(url, timeout=20, verify=verify)
            resp.raise_for_status()
            dados = resp.json()
            if not isinstance(dados, list):
                raise RuntimeError("Resposta inesperada do BCB.")
            return dados
        except requests.exceptions.SSLError:
            if verify:
                continue   # tenta sem SSL na próxima iteração
            raise RuntimeError("Falha SSL mesmo sem verificação de certificado.")
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Sem conexão com a internet ou BCB indisponível.")
        except requests.exceptions.Timeout:
            raise RuntimeError("Tempo esgotado ao acessar o BCB (timeout 20s).")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Erro HTTP {e.response.status_code} ao acessar BCB.")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Erro inesperado: {e}")
    return []  # nunca atingido

def calcular_fator(serie: list[dict]) -> tuple[Decimal, int]:
    """Retorna (fator acumulado, qtd de meses usados)."""
    fator = Decimal("1")
    meses = 0
    for ponto in serie:
        try:
            taxa = Decimal(str(ponto["valor"]))
            fator *= (1 + taxa / 100)
            meses += 1
        except Exception:
            pass
    return fator, meses

# ---------------------------------------------------------------------------
# Fluxo de uma consulta
# ---------------------------------------------------------------------------

def selecionar_indice() -> dict:
    cabecalho("Índices disponíveis")
    for i, idx in enumerate(INDICES, 1):
        print(f"  {Fore.WHITE}{i:2}.{Style.RESET_ALL}  "
              f"{Fore.YELLOW}{idx['nome']:<10}{Style.RESET_ALL}  {idx['desc']}")
    print()
    while True:
        raw = entrada(f"Escolha o índice (1–{len(INDICES)})")
        try:
            n = int(raw)
            if 1 <= n <= len(INDICES):
                return INDICES[n - 1]
        except ValueError:
            pass
        erro(f"Digite um número entre 1 e {len(INDICES)}.")

def obter_datas() -> tuple[date, date]:
    hoje = date.today()
    default_fim = f"{hoje.month:02}/{hoje.year}"

    while True:
        raw = entrada("Data inicial (MM/AAAA)")
        try:
            data_ini = parse_mes_ano(raw)
            break
        except ValueError as e:
            erro(str(e))

    while True:
        raw = entrada("Data final   (MM/AAAA)", default=default_fim)
        try:
            data_fim = parse_mes_ano(raw)
        except ValueError as e:
            erro(str(e))
            continue
        if data_fim < data_ini:
            erro("A data final deve ser igual ou posterior à data inicial.")
            continue
        if data_fim > hoje:
            aviso("Data final além do mês corrente — o índice pode não estar publicado ainda.")
        break

    return data_ini, data_fim

def obter_valor() -> Decimal:
    while True:
        raw = entrada("Valor original (R$)")
        try:
            return parse_valor(raw)
        except ValueError as e:
            erro(str(e))

def _exibir_indices_mensais(serie: list[dict], nome_indice: str) -> None:
    """Exibe tabela com o índice mensal e fator acumulado de cada mês do período."""
    cabecalho(f"Índices mensais — {nome_indice}")
    print(f"  {Fore.CYAN}{'Mês/Ano':<12} {'Índice (%)':>12}  {'Acumulado (%)':>14}{Style.RESET_ALL}")
    print(f"  {'─'*42}")

    fator_acum = Decimal("1")
    for ponto in serie:
        try:
            taxa = Decimal(str(ponto["valor"]))
        except Exception:
            continue
        fator_acum *= (1 + taxa / 100)
        acum_pct = (fator_acum - 1) * 100

        # Colorir negativos em vermelho
        cor = Fore.RED if taxa < 0 else Style.RESET_ALL
        print(f"  {ponto['data']:<12}"
              f" {cor}{float(taxa):>11.4f}%{Style.RESET_ALL}"
              f"  {float(acum_pct):>13.4f}%")

    print(f"  {'─'*42}")
    print(f"  {'Total':>12} {' ':>12}  {float((fator_acum-1)*100):>13.4f}%")


def executar_consulta() -> None:
    idx = selecionar_indice()

    cabecalho(f"Parâmetros — {idx['nome']}")
    data_ini, data_fim = obter_datas()
    valor_original = obter_valor()

    print()
    aviso(f"Consultando {idx['nome']} (série {idx['codigo']}) no BCB...")

    try:
        serie = buscar_serie(idx["codigo"], data_ini, data_fim)
    except RuntimeError as e:
        erro(str(e))
        return

    if not serie:
        erro(f"Nenhum dado retornado para {idx['nome']} no período informado.")
        aviso("Verifique se o índice já foi publicado para o período selecionado.")
        return

    fator, n_meses = calcular_fator(serie)
    variacao = (fator - 1) * 100
    valor_corrigido = (valor_original * fator).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    acrescimo = valor_corrigido - valor_original

    cabecalho("Resultado")
    larg = 22
    print(f"  {'Índice':<{larg}} {idx['nome']}  —  {idx['desc']}")
    print(f"  {'Período':<{larg}} {data_ini.strftime('%m/%Y')}  →  {data_fim.strftime('%m/%Y')}  "
          f"({n_meses} {'mês' if n_meses == 1 else 'meses'})")
    print(f"  {'Variação acumulada':<{larg}} {fmt_pct(variacao)}")
    print(f"  {'Fator de correção':<{larg}} {fator:.6f}")
    print()
    print(f"  {'Valor original':<{larg}} {fmt_brl(valor_original)}")
    print(f"  {'Acréscimo':<{larg}} {fmt_brl(acrescimo)}")
    print(f"  {Fore.GREEN}{'Valor corrigido':<{larg}} {fmt_brl(valor_corrigido)}{Style.RESET_ALL}")

    print()
    resp = entrada("Ver índices mensais do período? (S/N)", default="N").strip().upper()
    if resp == "S":
        _exibir_indices_mensais(serie, idx["nome"])

# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    # Forçar UTF-8 no terminal para suportar caracteres Unicode
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    init(autoreset=True)
    sep = "═" * 62
    print(f"\n{Fore.CYAN}{sep}")
    print(f"  {APP_NOME}  {APP_VERSAO}")
    print(f"  Fonte: Banco Central do Brasil — Sistema SGS")
    print(f"{sep}{Style.RESET_ALL}")

    while True:
        try:
            executar_consulta()
        except KeyboardInterrupt:
            break

        print()
        resp = entrada("Nova consulta? (S/N)", default="S").strip().upper()
        if resp != "S":
            break

    print(f"\n  {Fore.CYAN}Até logo!{Style.RESET_ALL}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()

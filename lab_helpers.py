"""
lab_helpers.py
--------------
Funções auxiliares para o LAB "Felicidade por Idade e por País".

Este módulo tenta baixar os dados reais (Our World in Data e Banco Mundial).
Se o download falhar (sem internet, API fora do ar, etc.), ele cai
automaticamente para dados SIMULADOS (synthetic=True), para que o pipeline
inteiro continue funcionando. NUNCA reporte números sintéticos como
descobertas sobre o mundo real -- eles servem só para testar o código.

Fontes reais (quando há internet disponível):
- Our World in Data, "Self-reported life satisfaction by age" (CC BY):
  https://ourworldindata.org/grapher/cantril-ladder-age-groups?tab=table
- Banco Mundial, API pública de indicadores:
  https://api.worldbank.org/v2/country/all/indicator/<CODE>
"""

from __future__ import annotations

import io
import warnings

import numpy as np
import pandas as pd
import requests

try:
    import country_converter as coco
    _CC = coco.CountryConverter()
except Exception:  # pragma: no cover - fallback se o pacote não estiver instalado
    _CC = None

RANDOM_STATE = 42

# --------------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------------

OWID_AGE_URL = (
    "https://ourworldindata.org/grapher/cantril-ladder-age-groups.csv"
    "?tab=table&csvType=full"
)

# Indicadores do Banco Mundial usados para enriquecer os dados por país.
WB_INDICATORS = {
    "gdp_pc": "NY.GDP.PCAP.PP.KD",   # PIB per capita, PPC (US$ int'l constantes)
    "pop": "SP.POP.TOTL",             # População total
    "area_km2": "AG.LND.TOTL.K2",     # Área terrestre (km²)
}

# Ponto médio (em anos) de cada faixa etária do OWID/WHR 2024.
# "60+" é uma faixa aberta; 70 é uma suposição documentada (ver Seção 6).
AGE_MID = {
    "Up to 29 years": 22,
    "30-44 years": 37,
    "45-59 years": 52,
    "60+ years": 70,
}

# Nomes "amigáveis" de faixa etária, para uso em gráficos e no rótulo age_group.
_AGE_GROUP_LABELS = {
    "Up to 29 years": "<30",
    "30-44 years": "30-44",
    "45-59 years": "45-59",
    "60+ years": "60+",
}

# Agregados regionais/de renda que a API do Banco Mundial mistura com países
# de verdade e que precisam ser descartados.
_WB_AGGREGATE_HINTS = (
    "World", "income", "IDA", "IBRD", "OECD", "Euro area", "European Union",
    "Arab World", "Africa", "Asia", "Europe", "America", "Caribbean",
    "Pacific", "Sub-Saharan", "Middle East", "small states", "Small states",
    "Least developed", "Fragile", "Heavily indebted", "Latin America",
    "North America", "South Asia", "Central Europe",
)


# --------------------------------------------------------------------------
# Conversão de país -> ISO3
# --------------------------------------------------------------------------

def to_iso3(names: pd.Series) -> pd.Series:
    """Converte uma coluna de nomes de país para códigos ISO3.

    Imprime, como aviso, a lista de nomes que não encontraram correspondência
    (por exemplo grafias incomuns ou territórios sem código ISO3 padrão).
    """
    names = pd.Series(names).astype(str)
    if _CC is None:
        raise ImportError("Instale 'country_converter' (pip install country_converter).")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        iso3 = pd.Series(_CC.convert(names.tolist(), to="ISO3", not_found=None), index=names.index)
    missing = names[iso3.isna()].unique().tolist()
    if missing:
        warnings.warn(f"Sem correspondência ISO3 para: {missing}")
    return iso3


# --------------------------------------------------------------------------
# Parte 1: dados de felicidade por idade (Our World in Data)
# --------------------------------------------------------------------------

def _download_owid_age() -> pd.DataFrame:
    resp = requests.get(OWID_AGE_URL, timeout=20)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text))


def load_owid_age(url: str = OWID_AGE_URL) -> pd.DataFrame:
    """Baixa e organiza os dados de felicidade por idade do OWID.

    Retorna um DataFrame em formato LONGO com colunas:
    country, iso3, year, age_group, ladder_mean, window, synthetic

    Se o download falhar, cai para dados simulados.
    """
    try:
        raw = _download_owid_age()
        long = raw.melt(
            id_vars=["Entity", "Code", "Year"],
            value_vars=list(AGE_MID.keys()),
            var_name="age_group",
            value_name="ladder_mean",
        )
        long = long.rename(columns={"Entity": "country", "Code": "iso3", "Year": "year"})
        long = long.dropna(subset=["iso3", "ladder_mean"])
        long["window"] = "2021-2023 (OWID/WHR 2024)"
        long["synthetic"] = False
        long["age_group"] = long["age_group"].map(_AGE_GROUP_LABELS)
        return long.reset_index(drop=True)
    except Exception as exc:  # sem internet, domínio bloqueado, formato mudou, etc.
        warnings.warn(
            f"Não foi possível baixar os dados reais do OWID ({exc}). "
            "Usando dados SIMULADOS (synthetic=True) como Plano B."
        )
        return make_synthetic_age_data(build_country_table())


# --------------------------------------------------------------------------
# Parte 2: enriquecimento com indicadores do Banco Mundial
# --------------------------------------------------------------------------

def fetch_wb(indicator: str, start_year: int = 2019, end_year: int = 2023) -> pd.Series:
    """Busca um indicador do Banco Mundial para todos os países.

    Guarda, para cada país, o último valor não faltante entre start_year e
    end_year (a API costuma deixar o ano mais recente em branco).
    Retorna uma Series indexada por iso3.
    """
    url = (
        f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
        f"?date={start_year}:{end_year}&format=json&per_page=20000"
    )
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        raise ValueError(f"Resposta inesperada da API do Banco Mundial para {indicator}")

    records = payload[1]  # [0] = metadados de paginação, [1] = registros
    df = pd.DataFrame.from_records(records)
    df = df[["countryiso3code", "date", "value"]].dropna(subset=["value"])
    df["date"] = df["date"].astype(int)
    df = df.sort_values("date").drop_duplicates("countryiso3code", keep="last")
    return df.set_index("countryiso3code")["value"].rename(indicator)


def _is_wb_aggregate(name: str) -> bool:
    return any(hint.lower() in str(name).lower() for hint in _WB_AGGREGATE_HINTS)


def build_country_table(
    indicators: dict[str, str] = WB_INDICATORS,
    synthetic_n: int = 180,
) -> pd.DataFrame:
    """Monta a tabela de países com gdp_pc, pop e area_km2 (via API do Banco Mundial).

    Retorna colunas: iso3, country, gdp_pc, pop, area_km2, synthetic
    Cai para uma tabela SIMULADA se a API não estiver acessível.
    """
    try:
        series = {name: fetch_wb(code) for name, code in indicators.items()}
        table = pd.concat(series.values(), axis=1)
        table.columns = list(series.keys())
        table.index.name = "iso3"
        table = table.reset_index()

        if _CC is not None:
            names = _CC.convert(table["iso3"].tolist(), src="ISO3", to="name_short", not_found=None)
            table["country"] = names
        else:
            table["country"] = table["iso3"]

        table = table[~table["country"].apply(_is_wb_aggregate)]
        table = table.dropna(subset=["gdp_pc", "pop", "area_km2"], how="all")
        table["synthetic"] = False
        return table.reset_index(drop=True)
    except Exception as exc:
        warnings.warn(
            f"Não foi possível acessar a API do Banco Mundial ({exc}). "
            "Usando uma tabela de países SIMULADA como Plano B."
        )
        return _synthetic_country_table(n=synthetic_n)


def _synthetic_country_table(n: int = 180) -> pd.DataFrame:
    """Tabela de países com PIB/população/área plausíveis, mas 100% fictícios."""
    rng = np.random.default_rng(RANDOM_STATE)
    iso3 = [f"C{i:03d}" for i in range(n)]
    country = [f"Country {i:03d}" for i in range(n)]
    # PIB per capita log-normal (de ~800 a ~120.000 USD PPC)
    gdp_pc = rng.lognormal(mean=9.3, sigma=1.1, size=n).clip(500, 150_000)
    pop = rng.lognormal(mean=15.5, sigma=2.0, size=n).clip(10_000, 1.4e9)
    area_km2 = rng.lognormal(mean=11.5, sigma=2.3, size=n).clip(200, 1.7e7)
    return pd.DataFrame(
        {
            "iso3": iso3,
            "country": country,
            "gdp_pc": gdp_pc,
            "pop": pop,
            "area_km2": area_km2,
            "synthetic": True,
        }
    )


def make_synthetic_age_data(country_table: pd.DataFrame) -> pd.DataFrame:
    """Simula notas de felicidade por faixa etária, com uma curva em U plantada.

    Usa o PIB per capita real/simulado da tabela de países, soma uma curva em U
    na idade e ruído gaussiano. Marca todas as linhas com synthetic=True.
    NUNCA reporte esses números como descobertas sobre o mundo real.
    """
    rng = np.random.default_rng(RANDOM_STATE)
    rows = []
    for _, row in country_table.iterrows():
        log_gdp = np.log(max(row["gdp_pc"], 1.0))
        base = 2.5 + 0.55 * log_gdp  # riqueza empurra o nível geral para cima
        for age_group, mid in AGE_MID.items():
            u_curve = 0.00035 * (mid - 47) ** 2  # mínimo plantado perto dos 47 anos
            noise = rng.normal(0, 0.25)
            ladder = np.clip(base + u_curve + noise, 0, 10)
            rows.append(
                {
                    "country": row["country"],
                    "iso3": row["iso3"],
                    "year": 2023,
                    "age_group": _AGE_GROUP_LABELS.get(age_group, age_group),
                    "ladder_mean": round(float(ladder), 3),
                    "window": "simulado (synthetic=True)",
                    "synthetic": True,
                }
            )
    return pd.DataFrame(rows)

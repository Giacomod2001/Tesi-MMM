"""
Configurazione di pipeline: convenzioni e dimensioni canoniche.

Qui vivono SOLO le convenzioni condivise da tutti i moduli (ingestion,
model, allocator): geografia, calendario, valuta, nomi colonna canonici.
I parametri del mondo sintetico stanno in `generator/world.py`; i
parametri di fit in `model/`; i vincoli dell'allocator sono input utente.
"""
from __future__ import annotations

import os

# --------------------------------------------------------------- percorsi
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "pipeline", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")            # export (sintetici o reali)
CANON_DIR = os.path.join(DATA_DIR, "canonical")    # fatti canonici validati
OUTPUT_DIR = os.path.join(DATA_DIR, "output")      # fit, allocazioni, report
GROUND_TRUTH_JSON = os.path.join(DATA_DIR, "ground_truth.json")  # mai letta dal modello

# --------------------------------------------------------------- calendario
# Granularità del modello: settimana ISO che inizia il LUNEDÌ (W-MON).
# Mese e trimestre si ottengono per aggregazione, mai il giorno.
WEEK_FREQ = "W-MON"
QUARTER_WEEKS = 13          # finestra di pianificazione dell'allocator

# --------------------------------------------------------------- valuta
CURRENCY = "EUR"

# --------------------------------------------------------------- geografia
# Le 20 regioni italiane con quota di popolazione residente (ISTAT, ~2024).
# Le quote servono come fallback di ripartizione geografica della spesa
# (gerarchia di qualità n.3 nel documento di progetto) e per il generatore.
REGIONS: dict[str, float] = {
    "Lombardia": 0.169, "Lazio": 0.097, "Campania": 0.095, "Veneto": 0.082,
    "Sicilia": 0.081, "Emilia-Romagna": 0.075, "Piemonte": 0.072,
    "Puglia": 0.066, "Toscana": 0.062, "Calabria": 0.031, "Sardegna": 0.027,
    "Liguria": 0.025, "Marche": 0.025, "Abruzzo": 0.021,
    "Friuli-Venezia Giulia": 0.020, "Trentino-Alto Adige": 0.018,
    "Umbria": 0.014, "Basilicata": 0.009, "Molise": 0.005,
    "Valle d'Aosta": 0.002,
}
# normalizzazione difensiva (le quote pubblicate non sommano esattamente a 1)
_tot = sum(REGIONS.values())
REGIONS = {r: v / _tot for r, v in REGIONS.items()}

REGION_LIST = sorted(REGIONS)   # ordine canonico, stabile per Meridian

# Alias frequenti negli export reali → nome canonico. L'ingestion li usa
# come proposta; la conferma resta all'utente (human-in-the-middle).
REGION_ALIASES: dict[str, str] = {
    "emilia romagna": "Emilia-Romagna",
    "friuli venezia giulia": "Friuli-Venezia Giulia",
    "friuli": "Friuli-Venezia Giulia",
    "trentino alto adige": "Trentino-Alto Adige",
    "trentino-south tyrol": "Trentino-Alto Adige",
    "trentino": "Trentino-Alto Adige",
    "valle d aosta": "Valle d'Aosta",
    "aosta": "Valle d'Aosta",
    "aosta valley": "Valle d'Aosta",
    "apulia": "Puglia",
    "lombardy": "Lombardia",
    "piedmont": "Piemonte",
    "sicily": "Sicilia",
    "sardinia": "Sardegna",
    "tuscany": "Toscana",
    "latium": "Lazio",
    "the marches": "Marche",
}

# --------------------------------------------------------------- fatti canonici
# Nomi colonna canonici. Una riga = settimana × regione (× canale × campagna
# nel fatto media). Date ISO 8601, valuta EUR.
MEDIA_COLS = ["week", "region", "channel", "campaign",
              "spend", "impressions", "clicks", "platform_conversions"]
OUTCOME_COLS = ["week", "region", "conversions", "revenue"]
DEMAND_COLS = ["week", "region", "client_requests", "candidate_searches"]
SEASONALITY_COLS = ["week", "region", "seasonal_index"]   # region opzionale ("*")

# Attributi della dimensione campagna (anagrafica, non serie storica)
CAMPAIGN_ATTR_COLS = ["campaign", "channel", "objective", "funnel", "geo_targeted"]

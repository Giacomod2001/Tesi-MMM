"""
Il "mondo sintetico": parametri veri del processo generativo.

Tutto ciò che il modello dovrà stimare è definito qui e SOLO qui.
Il file ground_truth.json prodotto da run.py è una fotografia di questi
parametri (più le grandezze derivate, es. il ROI vero calcolato per
controfattuale): il modello non lo legge mai.

Calibrazione qualitativa per canale (settore staffing):
- google:   risposta diretta (search), adstock breve, ROI alto
- meta:     domanda latente, volumi alti, adstock medio, saturazione graduale
- linkedin: white collar / employer branding, ROI medio basso, coda lunga
- indeed:   job board, audience finita: satura presto, adstock breve
"""
from __future__ import annotations

import numpy as np

SEED = 42
N_WEEKS = 104                      # 2 anni
START_WEEK = "2024-01-01"          # lunedì

# --------------------------------------------------------------- canali
# beta   : conversioni incrementali massime a piena saturazione (naz./sett.)
# lam    : ritenzione adstock geometrico
# K_pc   : half-saturation di Hill sull'adstock PRO-CAPITE settimanale
#          (EUR per quota di popolazione; stessa curva per tutte le regioni,
#          assunzione coerente con la gerarchia geografica del modello)
# slope  : pendenza di Hill
# misattr: fattore di sovra/sotto-attribuzione delle conversioni di
#          piattaforma rispetto alle incrementali vere (bias noto dei ROAS)
CHANNELS: dict[str, dict] = {
    "google":   {"beta": 900.0,  "lam": 0.15, "K_pc": 16_000, "slope": 1.4,
                 "misattr": 1.30},
    "meta":     {"beta": 1000.0, "lam": 0.45, "K_pc": 26_000, "slope": 1.1,
                 "misattr": 1.65},
    "linkedin": {"beta": 280.0,  "lam": 0.55, "K_pc": 14_000, "slope": 1.3,
                 "misattr": 0.85},
    "indeed":   {"beta": 650.0,  "lam": 0.20, "K_pc": 7_000,  "slope": 1.8,
                 "misattr": 1.10},
}

# Spesa settimanale media nazionale per canale (EUR)
MEAN_WEEKLY_SPEND = {"google": 12_000, "meta": 9_000,
                     "linkedin": 5_000, "indeed": 8_000}

# --------------------------------------------------------------- campagne
# share    : quota della spesa di canale
# geo      : True = geo-targettizzata (spesa regionale reale negli export)
# quality  : moltiplicatore di efficacia relativa intra-canale; pesa le
#            conversioni di piattaforma → è ciò che lo stage 2 deve recuperare
# cpm      : EUR per 1000 impression (per generare le impression)
# ctr      : click-through rate
# objective, funnel: attributi anagrafici della dimensione campagna
CAMPAIGNS: dict[str, dict] = {
    "search_jobs":      {"channel": "google",   "share": 0.50, "geo": True,
                         "quality": 1.30, "cpm": 38.0, "ctr": 0.052,
                         "objective": "candidature", "funnel": "lower"},
    "search_brand":     {"channel": "google",   "share": 0.20, "geo": False,
                         "quality": 1.05, "cpm": 30.0, "ctr": 0.065,
                         "objective": "brand", "funnel": "lower"},
    "pmax":             {"channel": "google",   "share": 0.30, "geo": False,
                         "quality": 0.80, "cpm": 12.0, "ctr": 0.018,
                         "objective": "candidature", "funnel": "mid"},
    "daba":             {"channel": "meta",     "share": 0.45, "geo": True,
                         "quality": 1.15, "cpm": 7.5,  "ctr": 0.014,
                         "objective": "candidature", "funnel": "mid"},
    "lead_gen":         {"channel": "meta",     "share": 0.35, "geo": True,
                         "quality": 1.20, "cpm": 9.0,  "ctr": 0.011,
                         "objective": "lead", "funnel": "lower"},
    "brand_awareness":  {"channel": "meta",     "share": 0.20, "geo": False,
                         "quality": 0.55, "cpm": 4.5,  "ctr": 0.006,
                         "objective": "brand", "funnel": "upper"},
    "sponsored_content":{"channel": "linkedin", "share": 0.60, "geo": False,
                         "quality": 0.90, "cpm": 28.0, "ctr": 0.007,
                         "objective": "brand", "funnel": "upper"},
    "lead_forms":       {"channel": "linkedin", "share": 0.40, "geo": False,
                         "quality": 1.15, "cpm": 34.0, "ctr": 0.009,
                         "objective": "lead", "funnel": "lower"},
    "sponsored_jobs":   {"channel": "indeed",   "share": 0.80, "geo": True,
                         "quality": 1.10, "cpm": 22.0, "ctr": 0.041,
                         "objective": "candidature", "funnel": "lower"},
    "display":          {"channel": "indeed",   "share": 0.20, "geo": False,
                         "quality": 0.60, "cpm": 6.0,  "ctr": 0.004,
                         "objective": "brand", "funnel": "upper"},
}

# --------------------------------------------------------------- baseline
BASELINE = {
    "alpha_national": 6_500.0,   # candidature organiche/settimana (nazionale)
    "trend_per_week": 4.0,       # lieve crescita strutturale
    "region_sd": 0.18,           # eterogeneità regionale (moltiplicativa, lognorm)
}

# Valore di una candidatura (EUR di margine atteso: tasso di inserimento
# x margine della missione). Gamma con questa media e cv.
REVENUE_PER_CONVERSION = {"mean": 40.0, "cv": 0.65}

# --------------------------------------------------------------- controlli
DEMAND = {
    "client_requests":   {"level": 2_400, "trend": 1.2, "seas_coupling": 0.55,
                          "noise_sd": 90,  "coef_true": 0.22},
    "candidate_searches":{"level": 5_200, "trend": -1.0, "seas_coupling": 0.80,
                          "noise_sd": 160, "coef_true": 0.10},
}
# coef_true = effetto sulle candidature per unità di scostamento dalla media
# (entra additivamente nella baseline regionale, riparametrizzato per quota pop.)

NOISE_SD_PC = 28.0   # sd del rumore osservazionale (scala nazionale; per
                     # regione viene scalato con sqrt(quota popolazione))


# --------------------------------------------------------------- stagionalità
def seasonal_curve(week_of_year: np.ndarray) -> np.ndarray:
    """Indice stagionale moltiplicativo del mercato staffing (media ~ 1).

    Picchi: gennaio (riaperture contratti) e settembre (rientro estivo).
    Cali: agosto (fermo produttivo) e settimane di Natale.
    """
    w = np.asarray(week_of_year, dtype=float)

    def bump(center, width, height):
        d = np.minimum(np.abs(w - center), 52 - np.abs(w - center))
        return height * np.exp(-0.5 * (d / width) ** 2)

    idx = (1.0
           + bump(2, 2.5, 0.28)      # picco gennaio
           + bump(36, 2.5, 0.32)     # picco settembre
           - bump(32, 2.0, 0.38)     # crollo agosto
           - bump(51.5, 1.2, 0.30))  # festività natalizie
    return idx / idx.mean()


# --------------------------------------------------------------- adstock/hill
def geometric_adstock(x: np.ndarray, lam: float) -> np.ndarray:
    out = np.empty_like(x, dtype=float)
    carry = 0.0
    for t in range(len(x)):
        carry = x[t] + lam * carry
        out[t] = carry
    return out


def hill(x: np.ndarray, K: float, slope: float) -> np.ndarray:
    x = np.maximum(np.asarray(x, dtype=float), 0.0)
    return x ** slope / (K ** slope + x ** slope + 1e-12)

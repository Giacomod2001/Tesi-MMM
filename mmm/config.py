"""
Configurazione della pipeline MMM — caso Randstad Italia (dati sintetici).

I parametri "veri" (TRUE_PARAMS) sono quelli usati dal generatore di dati
sintetici. Il modello, in fase di fit, NON li conosce: servono solo come
ground truth per la validazione (parameter recovery, cap. 4).

Calibrazione qualitativa per canale (cap. 3.3.2):
- indeed:   job board, audience finita -> satura presto (K basso), adstock breve
- google:   risposta diretta -> adstock breve, ROI alto
- meta:     domanda latente, volumi alti -> adstock medio, saturazione graduale
- linkedin: white collar / employer branding -> ROI medio piu' basso, coda lunga
"""

CHANNELS = ["google", "meta", "linkedin", "indeed"]

# Spesa settimanale media di riferimento (EUR) usata dal generatore
MEAN_WEEKLY_SPEND = {
    "google": 12_000,
    "meta": 9_000,
    "linkedin": 5_000,
    "indeed": 8_000,
}

# Parametri veri del processo generativo
# beta  : effetto massimo del canale (candidature/settimana a saturazione piena)
# lam   : tasso di ritenzione adstock geometrico (0=effimero, 1=persistente)
# K     : half-saturation della funzione di Hill, in EUR di adstock
# s     : slope della funzione di Hill
TRUE_PARAMS = {
    "google":   {"beta": 350.0, "lam": 0.15, "K": 18_000, "s": 1.4},
    "meta":     {"beta": 450.0, "lam": 0.45, "K": 30_000, "s": 1.1},
    "linkedin": {"beta": 220.0, "lam": 0.55, "K": 12_000, "s": 1.3},
    "indeed":   {"beta": 250.0, "lam": 0.20, "K": 7_000,  "s": 1.8},
}

# Baseline organica (candidature spontanee: brand, passaparola, filiali)
BASELINE = {
    "alpha": 1200.0,        # livello medio
    "trend_per_week": 0.8, # lieve trend strutturale
    "seas_amp": 150.0,     # ampiezza stagionalita' annuale
    "seas_amp2": 60.0,     # seconda armonica (picchi estivi/natalizi)
}

NOISE_SD = 35.0   # rumore osservazionale sulle candidature
N_WEEKS = 156     # 3 anni di osservazioni settimanali
SEED = 42

# File di output
DATA_CSV = "data/synthetic_weekly.csv"
TRUE_PARAMS_JSON = "data/true_params.json"
FIT_JSON = "output/fitted_params.json"
ALLOCATION_CSV = "output/allocation.csv"

# Variabili di controllo (cap. 3.1, termine gamma_j * z_j,t):
# - richieste_clienti: domanda di fulfillment da parte delle aziende clienti
# - ricerche_lavoratori: intensita' di ricerca lavoro lato candidati
CONTROLS = ["richieste_clienti", "ricerche_lavoratori"]
TRUE_CONTROL_COEF = {"richieste_clienti": 0.15, "ricerche_lavoratori": 0.08}

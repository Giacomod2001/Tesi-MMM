"""
MTA — Multi-Touch Attribution con catene di Markov (livello tattico).

Architettura decisionale a due livelli:
- Livello 1 (strategico, MMM): quanto budget al CANALE
- Livello 2 (tattico, MTA):   come ripartirlo tra le CAMPAGNE del canale

Metodo: il percorso utente e' modellato come catena di Markov assorbente
con stati = touchpoint osservati + {START, CONV, NULL}. Il contributo di
ogni touchpoint e' il suo REMOVAL EFFECT (Anderl et al., 2016): di quanto
cala la probabilita' complessiva di conversione se quel touchpoint viene
rimosso dal grafo. L'attribution puo' essere calcolata sia sul VOLUME
(numero di conversioni) sia sulla UTILITY (fatturato atteso).

Agnosticismo: nessun nome di canale o campagna e' hardcodato. Gli stati
vengono scoperti dai dati; il canale di una campagna e' ricavato dal
prefisso "canale:campagna" se presente, altrimenti la campagna e' essa
stessa il canale. L'ingestione riconosce da sola, in un CSV qualsiasi,
la colonna dei percorsi (separatore '>'), quella di conversione e quella
di valore.
"""
import json
import re

import numpy as np
import pandas as pd

ABSORBING = ("CONV", "NULL")


# ------------------------------------------------------------ ingestione agnostica
def detect_path_schema(df: pd.DataFrame) -> dict:
    """Riconosce le colonne di un dataset di percorsi qualsiasi."""
    path_col, best = None, 0.0
    for c in df.columns:
        if df[c].dtype == object:
            share = df[c].astype(str).str.contains(">").mean()
            if share > best and share > 0.3:
                path_col, best = c, share
    conv_col = None
    for c in df.columns:
        if c == path_col:
            continue
        vals = df[c].astype(str).str.lower().unique()[:50]
        if df[c].dtype == bool or set(vals) <= {"0", "1", "true", "false"}:
            conv_col = c; break
        if df[c].dtype == object and any(
                re.search(r"application|conv|purchase|won", str(v)) for v in vals):
            conv_col = c; break
    value_col = None
    candidates = []
    for c in df.columns:
        if c in (path_col, conv_col) or re.search(r"(?i)\b(id|uid|code|codice)\b|_id$|^id_", str(c)):
            continue
        v = pd.to_numeric(df[c], errors="coerce")
        if v.notna().mean() > 0.9 and (v.fillna(0) >= 0).all() and v.nunique() > 20:
            # esclude contatori/progressivi (quasi-monotoni, tutti interi distinti)
            vv = v.dropna()
            if (vv.diff().dropna() >= 0).mean() > 0.95 and vv.nunique() > 0.9 * len(vv):
                continue
            named = bool(re.search(r"(?i)util|value|valore|revenue|fatturato|ricav", str(c)))
            candidates.append((named, c))
    if candidates:
        candidates.sort(reverse=True)        # preferisce i nomi espliciti
        value_col = candidates[0][1]
    if path_col is None:
        raise ValueError("Nessuna colonna di percorsi riconosciuta "
                         "(attesa una colonna con tocchi separati da '>').")
    return {"path": path_col, "conversion": conv_col, "value": value_col}


def to_aggregates(df: pd.DataFrame, schema: dict | None = None) -> dict:
    """Da un dataframe di percorsi alle statistiche di transizione."""
    schema = schema or detect_path_schema(df)
    paths = df[schema["path"]].astype(str)
    if schema["conversion"] is None:
        conv = pd.Series(True, index=df.index)
    else:
        col = df[schema["conversion"]]
        if col.dtype == object:
            conv = col.astype(str).str.lower().str.contains(
                r"application|conv|true|won|purchase|1")
        else:
            conv = col.astype(bool)
    value = (pd.to_numeric(df[schema["value"]], errors="coerce").fillna(0)
             if schema["value"] else conv.astype(float))

    trans: dict = {}
    for path, cv in zip(paths, conv):
        prev = "START"
        for s in path.split(">"):
            s = s.strip()
            trans.setdefault(prev, {}).setdefault(s, 0)
            trans[prev][s] += 1
            prev = s
        end = "CONV" if cv else "NULL"
        trans.setdefault(prev, {}).setdefault(end, 0)
        trans[prev][end] += 1
    return {"transitions": trans,
            "total_conversions": int(conv.sum()),
            "total_utility": float(value[conv].sum()),
            "n_paths": int(len(df))}


# ------------------------------------------------------------------ catena di Markov
def _conversion_prob(trans: dict, removed: str | None = None) -> float:
    """P(assorbimento in CONV partendo da START), con stato opzionalmente rimosso.

    Risolve il sistema lineare p(s) = sum_t P(s->t) p(t), p(CONV)=1, p(NULL)=0.
    La rimozione di uno stato reindirizza i suoi ingressi verso NULL.
    """
    states = sorted({s for s in trans} | {t for d in trans.values() for t in d}
                    - set(ABSORBING))
    if removed in states:
        states.remove(removed)
    idx = {s: i for i, s in enumerate(states)}
    n = len(states)
    A = np.eye(n)
    b = np.zeros(n)
    for s in states:
        out = trans.get(s, {})
        tot = sum(out.values())
        if tot == 0:
            continue
        for t, c in out.items():
            p = c / tot
            if t == removed:
                continue                      # massa verso NULL
            elif t == "CONV":
                b[idx[s]] += p
            elif t == "NULL":
                pass
            elif t in idx:
                A[idx[s], idx[t]] -= p
    if "START" not in idx:
        return 0.0
    sol = np.linalg.solve(A, b)
    return float(sol[idx["START"]])


def attribution(agg: dict, metric: str = "volume") -> pd.DataFrame:
    """Attribution per touchpoint via removal effect, normalizzato.

    metric: 'volume' (conversioni) o 'utility' (fatturato atteso).
    """
    trans = agg["transitions"]
    base = _conversion_prob(trans)
    touchpoints = sorted({s for s in trans if s != "START"}
                         | {t for d in trans.values() for t in d
                            if t not in ABSORBING})
    rem = {}
    for tp in touchpoints:
        p = _conversion_prob(trans, removed=tp)
        rem[tp] = max(0.0, 1 - (p / base if base > 0 else 0))
    tot_rem = sum(rem.values()) or 1.0
    total = agg["total_utility"] if metric == "utility" else agg["total_conversions"]

    rows = []
    for tp, r in rem.items():
        channel = tp.split(":")[0] if ":" in tp else tp
        rows.append({"touchpoint": tp, "canale": channel,
                     "removal_effect": r,
                     "quota": r / tot_rem,
                     "attribuito": r / tot_rem * total})
    out = pd.DataFrame(rows).sort_values("attribuito", ascending=False)
    out.attrs["metric"] = metric
    out.attrs["base_conversion_prob"] = base
    return out


def split_channel_budget(attr: pd.DataFrame, channel_budgets: dict) -> pd.DataFrame:
    """Livello tattico: ripartisce il budget di OGNI canale (deciso dal MMM)
    tra le sue campagne, in proporzione all'attribution Markov.

    channel_budgets: {canale: budget} — tipicamente l'output dell'allocator MMM.
    I canali presenti nei percorsi ma assenti dal piano MMM (es. organico)
    vengono ignorati; il matching e' case-insensitive e tollerante.
    """
    def norm(s): return re.sub(r"\W+", "", str(s)).lower()
    budget_map = {norm(k): (k, v) for k, v in channel_budgets.items()}
    rows = []
    for canale, grp in attr.groupby("canale"):
        m = budget_map.get(norm(canale))
        if m is None:
            continue
        label, budget = m
        q = grp["quota"] / grp["quota"].sum()
        for (_, r), share in zip(grp.iterrows(), q):
            rows.append({"canale": label, "campagna": r["touchpoint"],
                         "quota_intra_canale": float(share),
                         "budget_campagna": float(share) * float(budget),
                         "attribuito": r["attribuito"]})
    return pd.DataFrame(rows).sort_values(["canale", "budget_campagna"],
                                          ascending=[True, False])


def load_aggregates(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

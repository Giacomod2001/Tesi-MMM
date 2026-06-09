"""
Test locale end-to-end della pipeline, inclusa l'ingestione dei file
di esempio in data/esempi/ (Excel, CSV, PDF).

Esecuzione:  python test_locale.py

I file di esempio riproducono i formati attesi dalle funzioni aziendali:
- richieste_clienti.xlsx : 12 osservazioni MENSILI, mesi italiani estesi
  ("Gennaio 2024"), valori con separatore migliaia italiano ("2.150")
- ricerche.csv           : 20 osservazioni SETTIMANALI, date europee
  gg/mm/aaaa, separatore ';', virgola decimale
- fulfillment.pdf        : tabella mensile in notazione anno-mese ("2024-01")
"""
import os

import pandas as pd

import allocator
import config
import data_generator
import ingestion
import model

HERE = os.path.dirname(os.path.abspath(__file__))
ESEMPI = os.path.join(HERE, "data", "esempi")


def check(nome, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {nome}")
    assert cond, nome


def main():
    print("1) Ingestione dei file di esempio")
    files = [os.path.join(ESEMPI, f) for f in
             ("richieste_clienti.xlsx", "ricerche.csv", "fulfillment.pdf")]
    for f in files:
        serie = ingestion.load(f)
        check(f"{os.path.basename(f)}: {len(serie)} righe, "
              f"colonne {list(serie.columns)}", len(serie) >= 12 or len(serie) == 20)
    # valori chiave: il parsing italiano deve dare 2150, non 2.15
    xls = ingestion.load(files[0])
    check("separatore migliaia italiano (2.150 -> 2150)",
          float(xls.iloc[0, 0]) == 2150.0)

    print("2) Generazione dataset sintetico e merge dei controlli esterni")
    df = data_generator.generate()
    merged = ingestion.merge_controls(df, files)
    ctrl = [c for c in merged.columns if c.startswith("ctrl_")]
    check(f"controlli esterni aggiunti: {ctrl}", len(ctrl) >= 3)
    check("nessun valore mancante dopo il riallineamento settimanale",
          merged[ctrl].notna().all().all())

    print("3) Fit del modello (con controlli sintetici ed esterni)")
    fit_res = model.fit(merged)
    d = fit_res["diagnostics"]
    print(f"   R2={d['r2']:.4f}  NRMSE={d['nrmse']:.4f}  MAPE={d['mape']:.2%}")
    check("R2 > 0.9", d["r2"] > 0.9)

    print("4) Allocazione del budget (piano trimestrale, vincoli attivi)")
    cur = {ch: float(df[f"spend_{ch}"].mean()) for ch in config.CHANNELS}
    plan = allocator.plan_periods(
        fit_res["channels"], total_budget=sum(cur.values()) * 52,
        granularity="quarter", period_weights=[0.8, 1.0, 0.9, 1.3],
        current_spend=cur, min_spend={"linkedin": 2_000}, max_change_pct=0.5)
    s = plan.attrs["summary"]
    check(f"budget pianificato == budget richiesto "
          f"({s['budget_totale']:,.0f} EUR)",
          abs(s["budget_totale"] - sum(cur.values()) * 52) < 1.0)
    check("vincolo minimo LinkedIn rispettato",
          (plan[plan.canale == "linkedin"]["spesa_settimanale"] >= 2_000 - 1e-6).all())
    print(f"   candidature attese sul piano: {s['candidature_totali']:,.0f}")

    print("\nTutti i test sono passati.")


if __name__ == "__main__":
    main()

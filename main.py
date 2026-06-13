import pandas as pd
import json
from mmm.config import TRUE_PARAMS, MEAN_WEEKLY_SPEND
from mmm.data_generator import generate
from mmm import model
from core import mmm_bayes
from mmm import allocator
from results_xlsx import write_sheet, WORKBOOK, MONEY

TOTAL_WEEKLY_BUDGET = sum(MEAN_WEEKLY_SPEND.values())

def main():
    print("--- 1. GENERAZIONE DATI ---")
    df = generate(seed=42)
    channels = ["google", "meta", "linkedin", "indeed"]
    print(f"Dati generati: {len(df)} settimane.")

    print("\n--- 2. STIMA FREQUENTISTA (Curve di Risposta) ---")
    res_freq = model.fit(df, channels)
    print("Parametri stimati (Beta e Adstock):")
    for ch, params in res_freq["channels"].items():
        print(f"  {ch}: beta={params['beta']:.4f}, lam={params['lam']:.2f}")

    print("\n--- 3. INFERENZA BAYESIANA (MCMC) ---")
    try:
        res_bayes = mmm_bayes.fit_bayes(df, channels, anchor=res_freq["channels"], draws=100, tune=100, chains=2)
        print("MCMC Completato. Risultati (Media e Incertezza Adstock):")
        for ch in channels:
            b_mean = res_bayes["summary"][f"beta_{ch}"]["mean"]
            l_mean = res_bayes["summary"][f"lam_{ch}"]["mean"]
            l_hdi = f"[{res_bayes['summary'][f'lam_{ch}']['hdi_5%']:.2f}, {res_bayes['summary'][f'lam_{ch}']['hdi_95%']:.2f}]"
            print(f"  {ch}: beta={b_mean:.4f}, lam={l_mean:.2f} (HDI 90%: {l_hdi})")
    except Exception as e:
        print(f"Errore Bayesiano: {e}")

    print("\n--- 4. OTTIMIZZAZIONE BUDGET (Allocatore) ---")
    # Usiamo i risultati frequentisti per l'ottimizzazione (o bayesiani se si preferisce)
    current_spend = {ch: float(df[f"spend_{ch}"].mean()) for ch in channels}
    plan_df = allocator.optimize_budget(res_freq["channels"], current_spend=current_spend, total_budget=TOTAL_WEEKLY_BUDGET)
    print(f"Budget totale settimanale: {TOTAL_WEEKLY_BUDGET} EUR")
    print("Ripartizione ottimale suggerita:")
    print(plan_df[["canale", "spesa_ottimale", "variazione_pct"]].to_string(index=False))
    print(f"Candidature totali stimate post-ottimizzazione: {plan_df.attrs['summary']['candidature_ottimali']:.0f}")

    write_sheet("Ottimizzazione", plan_df.round(2),
                {"spesa_ottimale": MONEY, "spesa_attuale": MONEY,
                 "variazione_pct": "0.0%"})
    print("\n[+] Foglio Ottimizzazione aggiornato in", WORKBOOK)

    print("\n--- PIPELINE COMPLETATA CON SUCCESSO ---")

if __name__ == "__main__":
    main()

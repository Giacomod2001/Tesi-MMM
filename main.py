import pandas as pd
import json
from mmm.config import TRUE_PARAMS, MEAN_WEEKLY_SPEND
from mmm.data_generator import generate_data
from core import model, mmm_bayes
from mmm import allocator

TOTAL_WEEKLY_BUDGET = sum(MEAN_WEEKLY_SPEND.values())

print("--- 1. GENERAZIONE DATI ---")
df = generate_data(weeks=104, random_seed=42)
channels = ["google", "meta", "linkedin", "indeed"]
print(f"Dati generati: {len(df)} settimane.")

print("\n--- 2. STIMA FREQUENTISTA (Curve di Risposta) ---")
res_freq = model.fit_model(df, channels)
print("Parametri stimati (Beta e Asintoto):")
for ch, params in res_freq["channels"].items():
    print(f"  {ch}: beta={params['beta']:.4f}, L={params['L']:.0f}")

print("\n--- 3. INFERENZA BAYESIANA (MCMC) ---")
try:
    res_bayes = mmm_bayes.fit_bayes(df, channels, anchor=res_freq["channels"], draws=100, tune=100, chains=2)
    print("MCMC Completato. Risultati:")
    for ch, params in res_bayes["channels"].items():
        print(f"  {ch}: beta={params['beta']:.4f}, L={params['L']:.0f} (Hdi 90%: {params['hdi_90_L']})")
except Exception as e:
    print(f"Errore Bayesiano: {e}")

print("\n--- 4. OTTIMIZZAZIONE BUDGET (Allocatore) ---")
# Usiamo i risultati frequentisti per l'ottimizzazione (o bayesiani se si preferisce)
res_opt, plan_df = allocator.optimize_budget(res_freq["channels"], total_budget=TOTAL_WEEKLY_BUDGET)
print(f"Budget totale settimanale: {TOTAL_WEEKLY_BUDGET} €")
print("Ripartizione ottimale suggerita:")
print(plan_df[["canale", "spesa_ottimale", "variazione_pct"]].to_string(index=False))
print(f"Candidature totali stimate post-ottimizzazione: {res_opt['total_candidature']:.0f}")

plan_df.to_csv("output_ottimizzazione.csv", index=False)
print("\n[+] Risultati dell'ottimizzazione salvati in 'output_ottimizzazione.csv'")

print("\n--- PIPELINE COMPLETATA CON SUCCESSO ---")

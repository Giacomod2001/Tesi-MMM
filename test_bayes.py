import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.abspath("."))

from core.mmm_bayes import fit_bayes
import pandas as pd
from app import store
import json

df = pd.read_csv("mmm/data/synthetic_weekly.csv")
channels = ["google", "meta", "linkedin", "indeed"]

print("Avvio fit_bayes...")
try:
    res = fit_bayes(df, channels, anchor=None, draws=10, tune=10, chains=1)
    print("fit_bayes completato con successo!")
except Exception as e:
    import traceback
    traceback.print_exc()

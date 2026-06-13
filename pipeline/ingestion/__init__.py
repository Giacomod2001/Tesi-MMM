"""
Ingestion: dagli export eterogenei ai fatti canonici.

Catena:  parser → mappatura proposta + CONFERMA UMANA → normalizzazione
         → pseudonimizzazione (GDPR) → ripartizione geografica
         → validazione → fatti canonici (schema.py)

È l'unico punto della pipeline che tocca i formati di origine: a valle
esiste solo lo schema canonico. La mappatura confermata viene salvata su
file (audit trail) e riusata nei rilanci successivi.
"""

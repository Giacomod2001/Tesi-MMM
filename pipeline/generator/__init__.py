"""
Generatore del dataset sintetico (solo fase tesi).

Produce 2 anni di dati realistici per il settore staffing con verità
nascosta nota (`ground_truth.json`), e li serializza come export "sporchi"
che imitano i formati reali delle piattaforme — il banco di prova
dell'ingestion. Con i dati reali questo modulo si elimina e il resto
della pipeline non cambia.
"""

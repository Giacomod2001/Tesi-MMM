"""
Budget allocator trimestrale (finestra di 13 settimane) a due stadi.

Stage 1 (quarter.py)  : allocazione ottima del budget tra i CANALI, con
                        vincoli min/max in EUR. Percorso primario:
                        BudgetOptimizer nativo di Meridian; fallback
                        equivalente su curve posterior (stesso output).
Spaccato (schedule.py): distribuzione dell'ottimo su settimane e mesi
                        seguendo la stagionalità esogena.
Stage 2 (campaigns.py): riparto del budget di canale tra le CAMPAGNE
                        riscalando i ROAS di piattaforma sul ROI di
                        canale stimato dal MMM.

Ogni output è una RACCOMANDAZIONE: la decisione resta al manager
(human-in-the-middle).
"""

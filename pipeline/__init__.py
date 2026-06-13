"""
Pipeline MMM + Budget Allocator — caso Randstad Italia.

Architettura (vedi documento di progetto):

    generator/   dati sintetici con ground truth nota   (solo fase tesi)
    ingestion/   parser → mappatura confermata → validazione → panel
    model/       Meridian, MMM bayesiano geo-gerarchico a livello canale
    allocator/   ottimizzazione trimestrale + stage 2 per campagna
    validation/  parameter recovery vs ground truth     (solo fase tesi)

Il modello è data-agnostic: vede solo il panel canonico regione × settimana
definito in `schema.py` e non sa mai se i dati sono sintetici o reali.
"""

__version__ = "1.0.0"

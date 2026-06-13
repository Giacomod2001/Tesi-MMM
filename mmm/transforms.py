"""
Trasformazioni fondamentali del MMM (cap. 3.2 e 3.3):
- adstock geometrico (Broadbent, 1979)
- saturazione di Hill

L'ordine di applicazione e' fisso: spesa -> adstock -> saturazione -> beta.
"""
import numpy as np


def geometric_adstock(x: np.ndarray, lam: float) -> np.ndarray:
    """Adstock geometrico: A(t) = x(t) + lam * A(t-1).

    lam in [0,1): tasso di ritenzione. lam=0 -> effetto solo nel periodo
    di erogazione; lam->1 -> effetto molto persistente.
    """
    out = np.empty_like(x, dtype=float)
    carry = 0.0
    for t in range(len(x)):
        carry = x[t] + lam * carry
        out[t] = carry
    return out


def hill(x: np.ndarray, K: float, s: float) -> np.ndarray:
    """Funzione di Hill: f(x) = x^s / (K^s + x^s), in [0,1).

    K = half-saturation (spesa-adstock a cui si ottiene il 50% dell'effetto
    massimo); s = slope (ripidita' della curva).
    """
    x = np.maximum(x, 0.0)
    return x**s / (K**s + x**s + 1e-12)


def channel_response(spend: np.ndarray, beta: float, lam: float,
                     K: float, s: float) -> np.ndarray:
    """Contributo settimanale del canale: beta * Hill(Adstock(spesa))."""
    return beta * hill(geometric_adstock(spend, lam), K, s)


def steady_state_response(weekly_spend: float, beta: float, lam: float,
                          K: float, s: float) -> float:
    """Risposta a regime per spesa settimanale costante.

    Con spesa costante x, l'adstock converge a x / (1 - lam).
    E' la curva su cui lavora l'ottimizzatore di budget (cap. 3.5).
    """
    A = weekly_spend / (1.0 - lam)
    return float(beta * hill(np.array([A]), K, s)[0])


def marginal_response(weekly_spend: float, beta: float, lam: float,
                      K: float, s: float, eps: float = 1.0) -> float:
    """ROAS marginale: candidature incrementali dell'ultimo euro/settimana."""
    up = steady_state_response(weekly_spend + eps, beta, lam, K, s)
    dn = steady_state_response(weekly_spend, beta, lam, K, s)
    return (up - dn) / eps

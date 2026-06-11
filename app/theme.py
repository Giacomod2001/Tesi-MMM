"""Tema visivo Randstad condiviso per i grafici Plotly (sfondo chiaro)."""
import plotly.graph_objects as go

# Palette serie dati: ordine fisso, stesso canale = stesso colore ovunque.
# Colori saturi e leggibili su sfondo chiaro, di famiglie diverse:
# google rosso, meta blu, linkedin verde, indeed arancio.
COLORS = ["#D32F2F", "#1976D2", "#2E7D32", "#F57C00",
          "#7B1FA2", "#C2185B", "#00838F"]
BG = "rgba(0,0,0,0)"          # eredita lo sfondo della card
GRID = "#E3E1DA"             # griglia leggera su chiaro
AXIS = "#5A6473"             # testo assi (muted, ma AA su chiaro)
FONT = "#1A2332"             # testo principale (ink)
FONT_FAMILY = "Tahoma, Geneva, Verdana, sans-serif"

POSITIVE = "#1E7E34"
WARNING = "#C77700"
NEGATIVE = "#C62828"


def dark(fig: go.Figure, height: int = 380) -> go.Figure:
    """Applica il tema (nome storico) ai grafici: ora sfondo chiaro."""
    fig.update_layout(
        template="plotly_white", paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=FONT, size=12, family=FONT_FAMILY), height=height,
        margin=dict(l=40, r=20, t=48, b=40), colorway=COLORS,
        legend=dict(orientation="h", y=1.12, x=0),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False,
                     tickfont=dict(color=AXIS), title_font=dict(color=AXIS))
    fig.update_yaxes(gridcolor=GRID, zeroline=False,
                     tickfont=dict(color=AXIS), title_font=dict(color=AXIS))
    return fig

"""Tema visivo Randstad condiviso per i grafici Plotly."""
import plotly.graph_objects as go

# Palette serie dati: ordine fisso, stesso canale = stesso colore ovunque.
COLORS = ["#003580", "#2196F3", "#4CAF50", "#FF9800",
          "#9C27B0", "#E91E63", "#00BCD4"]
BG = "rgba(0,0,0,0)"
GRID = "#2D3848"
AXIS = "#8B95A5"
FONT = "#E8ECF1"
FONT_FAMILY = "Tahoma, Geneva, Verdana, sans-serif"

POSITIVE = "#28A745"
WARNING = "#E8A317"
NEGATIVE = "#DC3545"


def dark(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=FONT, size=12, family=FONT_FAMILY), height=height,
        margin=dict(l=40, r=20, t=48, b=40), colorway=COLORS,
        legend=dict(orientation="h", y=1.12, x=0),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False,
                     tickfont=dict(color=AXIS), title_font=dict(color=AXIS))
    fig.update_yaxes(gridcolor=GRID, zeroline=False,
                     tickfont=dict(color=AXIS), title_font=dict(color=AXIS))
    return fig

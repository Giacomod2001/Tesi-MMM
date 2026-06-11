"""Tema scuro condiviso per i grafici Plotly."""
import plotly.graph_objects as go

COLORS = ["#4cc9f0", "#f72585", "#b5e48c", "#ffd166", "#9d4edd",
          "#06d6a0", "#ef476f", "#a5a58d"]
BG = "rgba(0,0,0,0)"
GRID = "#2a2e3a"
FONT = "#e8e9ed"


def dark(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=FONT, size=12), height=height,
        margin=dict(l=40, r=20, t=48, b=40), colorway=COLORS,
        legend=dict(orientation="h", y=1.12, x=0),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig

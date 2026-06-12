"""Tema scuro condiviso per i grafici Plotly."""
import plotly.graph_objects as go

ACCENT = "#3b82f6"          # blu aziendale: UNICO colore interattivo
COLORS = ["#3b82f6", "#93c5fd", "#64748b", "#cbd5e1",
          "#2563eb", "#94a3b8", "#1d4ed8", "#e2e8f0"]   # famiglia blu/neutri
DASHES = [None, "dash", "dot", "dashdot"]
SEMANTIC = {"ok": "#22c55e", "warn": "#eab308", "bad": "#ef4444"}
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

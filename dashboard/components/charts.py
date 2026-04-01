import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np


THEME = {
    "bg": "#0E1117",
    "paper": "#1A1F2E",
    "border": "#2D3445",
    "text": "#E8EAED",
    "muted": "#8B95A1",
    "orange": "#FF6B35",
    "green": "#00D4A8",
    "red": "#FF4C4C",
    "blue": "#4C9BE8",
    "yellow": "#FFB830",
}


def candlestick_chart(df, title="Price Chart", coin="BTC"):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index if hasattr(df.index, 'dtype') else df["timestamp"],
        open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color=THEME["green"], decreasing_line_color=THEME["red"],
        increasing_fillcolor=THEME["green"], decreasing_fillcolor=THEME["red"],
        name="OHLCV",
    ))

    if "volume" in df.columns:
        colors = [THEME["green"] if c >= o else THEME["red"]
                  for o, c in zip(df["open"], df["close"])]
        fig.add_trace(go.Bar(
            x=df.index if hasattr(df.index, 'dtype') else df["timestamp"],
            y=df["volume"], name="Volume",
            marker_color=colors, opacity=0.4, yaxis="y2",
        ))

    _apply_theme(fig, title)
    fig.update_layout(
        yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False, opacity=0.5),
        xaxis_rangeslider_visible=False,
    )
    return fig


def sentiment_time_series(df, coin="BTC"):
    fig = go.Figure()
    if df.empty:
        return fig

    fig.add_trace(go.Scatter(
        x=df["window_start"] if "window_start" in df.columns else df.index,
        y=df["avg_sentiment"], mode="lines+markers",
        name="Sentiment Score",
        line=dict(color=THEME["orange"], width=2),
        marker=dict(size=4),
        fill="tozeroy",
        fillcolor="rgba(255, 107, 53, 0.1)",
    ))
    fig.add_hline(y=0.5, line_dash="dash", line_color=THEME["muted"], opacity=0.5)
    _apply_theme(fig, f"{coin} Sentiment");
    fig.update_yaxes(range=[0, 1])
    return fig


def fear_greed_gauge(value):
    zones = {
        (0, 25): "#FF4C4C",
        (25, 45): "#FF7B54",
        (45, 55): "#FFB830",
        (55, 75): "#00D4A8",
        (75, 101): "#00FF9C",
    }
    color = "#FFB830"
    for (low, high), c in zones.items():
        if low <= value < high:
            color = c
            break

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        domain={"x": [0, 1], "y": [0, 1]},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": THEME["muted"]},
            "bar": {"color": color},
            "bgcolor": THEME["paper"],
            "bordercolor": THEME["border"],
            "steps": [
                {"range": [0, 25], "color": "rgba(255,76,76,0.15)"},
                {"range": [25, 45], "color": "rgba(255,123,84,0.15)"},
                {"range": [45, 55], "color": "rgba(255,184,48,0.15)"},
                {"range": [55, 75], "color": "rgba(0,212,168,0.15)"},
                {"range": [75, 100], "color": "rgba(0,255,156,0.15)"},
            ],
        },
        number={"font": {"color": color, "family": "Space Mono", "size": 36}},
    ))
    _apply_theme(fig, "Fear & Greed Index")
    fig.update_layout(height=250)
    return fig


def equity_curve_chart(equity_data, title="Portfolio Equity Curve"):
    df = pd.DataFrame(equity_data)
    if df.empty:
        return go.Figure()

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    start = df["equity"].iloc[0]
    df["return_pct"] = (df["equity"] - start) / start * 100

    fig = go.Figure()
    pos = df[df["return_pct"] >= 0]
    neg = df[df["return_pct"] < 0]

    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["equity"],
        mode="lines", name="Portfolio Value",
        line=dict(color=THEME["green"], width=2),
        fill="tozeroy", fillcolor="rgba(0, 212, 168, 0.08)",
    ))
    _apply_theme(fig, title)
    return fig


def prediction_accuracy_bar(df):
    if df.empty:
        return go.Figure()
    fig = px.bar(
        df, x="coin", y="accuracy", color="model_name",
        barmode="group", color_discrete_sequence=[THEME["orange"], THEME["blue"], THEME["green"]],
    )
    _apply_theme(fig, "Model Prediction Accuracy by Coin")
    fig.update_yaxes(range=[0, 1])
    return fig


def _apply_theme(fig, title=""):
    fig.update_layout(
        title=dict(text=title, font=dict(color=THEME["text"], size=14)),
        paper_bgcolor=THEME["paper"],
        plot_bgcolor=THEME["bg"],
        font=dict(family="Inter", color=THEME["text"]),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=THEME["border"]),
        xaxis=dict(gridcolor=THEME["border"], showgrid=True),
        yaxis=dict(gridcolor=THEME["border"], showgrid=True),
    )

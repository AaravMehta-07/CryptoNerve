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


def sentiment_heatmap_chart(heatmap_df, title="Live Sentiment Heatmap — All Coins"):
    """
    heatmap_df: DataFrame with columns: [coin, time_bucket, avg_sentiment]
    Produces a cross-coin × time color heatmap (PS2 §3.6 requirement).
    """
    if heatmap_df.empty:
        fig = go.Figure()
        _apply_theme(fig, title)
        return fig

    coins    = sorted(heatmap_df["coin"].unique(), reverse=True)
    times    = sorted(heatmap_df["time_bucket"].unique())
    z_matrix = []
    text_mat = []

    for coin in coins:
        row, trow = [], []
        cdf = heatmap_df[heatmap_df["coin"] == coin].set_index("time_bucket")
        for t in times:
            val = float(cdf.loc[t, "avg_sentiment"]) if t in cdf.index else 0.5
            row.append(val)
            label = "BULLISH" if val > 0.6 else "BEARISH" if val < 0.4 else "NEUTRAL"
            trow.append(f"{val:.2f} ({label})")
        z_matrix.append(row)
        text_mat.append(trow)

    time_labels = [str(t)[-8:-3] if len(str(t)) > 8 else str(t) for t in times]

    fig = go.Figure(go.Heatmap(
        z=z_matrix, x=time_labels, y=coins,
        text=text_mat, texttemplate="%{text}",
        hovertemplate="<b>%{y}</b> @ %{x}<br>Sentiment: %{z:.2f}<extra></extra>",
        colorscale=[
            [0.00, "#FF4C4C"],  # Extreme Bearish
            [0.30, "#FF7B54"],  # Bearish
            [0.50, "#2D3445"],  # Neutral
            [0.70, "#00A88A"],  # Bullish
            [1.00, "#00FF9C"],  # Extreme Bullish
        ],
        zmid=0.5, zmin=0.0, zmax=1.0,
        showscale=True,
        colorbar=dict(
            title=dict(text="Sentiment", font=dict(color=THEME["muted"])),
            tickvals=[0, 0.25, 0.5, 0.75, 1],
            ticktext=["Ext. Bear", "Bear", "Neutral", "Bull", "Ext. Bull"],
            tickfont=dict(color=THEME["muted"], size=10),
            bgcolor=THEME["paper"], bordercolor=THEME["border"],
        ),
        textfont=dict(size=9, color=THEME["text"]),
    ))
    _apply_theme(fig, title)
    fig.update_layout(
        height=max(180, len(coins) * 68),
        xaxis=dict(title="Time (UTC)", tickangle=-30, showgrid=False),
        yaxis=dict(showgrid=False),
    )
    return fig


def signal_radar_chart(sentiment, prediction, onchain, technical, coin="BTC", signal_type="HOLD"):
    """Polar / radar chart — 4 composite signal components for explainability."""
    categories = ["LLM Sentiment", "ML Prediction", "On-Chain", "Technicals", "LLM Sentiment"]
    values = [sentiment, prediction, onchain, technical, sentiment]  # close loop
    color_map = {
        "STRONG_BUY": THEME["green"], "BUY": THEME["green"],
        "HOLD": THEME["blue"],
        "SELL": THEME["red"], "STRONG_SELL": THEME["red"],
    }
    accent = color_map.get(signal_type, THEME["orange"])
    r, g, b = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values, theta=categories, fill="toself",
        fillcolor=f"rgba({r},{g},{b},0.18)",
        line=dict(color=accent, width=2),
        name=f"{coin} — {signal_type}",
    ))
    _apply_theme(fig, f"{coin} Signal Breakdown")
    fig.update_layout(
        polar=dict(
            bgcolor=THEME["bg"],
            radialaxis=dict(visible=True, range=[0, 1],
                           tickfont=dict(size=9, color=THEME["muted"]),
                           gridcolor=THEME["border"], linecolor=THEME["border"]),
            angularaxis=dict(tickfont=dict(size=10, color=THEME["text"]),
                            gridcolor=THEME["border"]),
        ),
        height=300,
    )
    return fig


def price_sparkline(prices, coin="BTC", color=None):
    """Compact 48px sparkline for the coin ticker row."""
    if not prices:
        return go.Figure()
    coin_colors = {"BTC": "#F7931A", "ETH": "#627EEA", "SOL": "#00FFA3",
                   "DOGE": "#C2A633", "XRP": "#00AAE4"}
    c = color or coin_colors.get(coin, THEME["orange"])
    r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
    fig = go.Figure(go.Scatter(
        x=list(range(len(prices))), y=prices, mode="lines",
        line=dict(color=c, width=1.5),
        fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.07)",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0), height=48,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


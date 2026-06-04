import json
import os

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from config import DATA_DIR
from design_system import format_price, format_sqm_price, format_pct, COLORS, apply_theme


def load_seoul_geo() -> dict:
    """서울 구 경계 GeoJSON을 로드한다."""
    path = os.path.join(DATA_DIR, "seoul_geo.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# 지표별 색상 스케일
_DIVERGING_METRICS = {"change_pct", "momentum_pct", "premium_pct"}


def create_choropleth(
    summary_df: pd.DataFrame,
    value_col: str = "median_price_per_sqm",
    legend_name: str = "중위 m2당 가격 (만원/m2)",
    tooltip_data: pd.DataFrame = None,
) -> go.Figure:
    """구별 요약 데이터를 Plotly choropleth로 시각화한다.

    Returns:
        go.Figure (folium 대신 plotly 사용).
    """
    geo_data = load_seoul_geo()

    # 색상 스케일
    if value_col in _DIVERGING_METRICS:
        color_scale = "RdBu"
        color_midpoint = 0
    else:
        color_scale = "Blues"
        color_midpoint = None

    # 툴팁 데이터 준비
    df = summary_df.copy()
    df["tooltip"] = df.apply(lambda r: (
        f"<b>{r['gu_name']}</b><br>"
        f"m2당: {format_sqm_price(r.get('median_price_per_sqm', 0))}<br>"
        f"중위가: {format_price(r.get('median_price', 0))}<br>"
        f"상승률: {format_pct(r.get('change_pct', 0))}<br>"
        f"거래: {int(r.get('trade_count', 0)):,}건"
    ), axis=1)

    fig = px.choropleth_mapbox(
        df,
        geojson=geo_data,
        locations="gu_name",
        featureidkey="properties.SIG_KOR_NM",
        color=value_col,
        color_continuous_scale=color_scale,
        color_continuous_midpoint=color_midpoint,
        mapbox_style="carto-positron",
        center={"lat": 37.5665, "lon": 126.9780},
        zoom=10,
        opacity=0.7,
        labels={value_col: legend_name},
        custom_data=["tooltip"],
    )

    fig.update_traces(
        hovertemplate="%{customdata[0]}<extra></extra>",
        marker_line_width=1,
        marker_line_color="white",
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=500,
        coloraxis_colorbar=dict(
            title=dict(text=legend_name, font=dict(size=10)),
            thickness=12,
            len=0.6,
            tickfont=dict(size=9),
        ),
    )

    return fig

import json
import os

import folium
import pandas as pd

from config import DATA_DIR
from design_system import format_price, format_sqm_price, format_pct, COLORS


def load_seoul_geo() -> dict:
    """서울 구 경계 GeoJSON을 로드한다."""
    path = os.path.join(DATA_DIR, "seoul_geo.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# 지표별 color scale 매핑
_COLOR_SCALES = {
    "sequential": "YlGnBu",
    "diverging": "RdBu",
}

# 음수/양수 양극이 의미 있는 지표들
_DIVERGING_METRICS = {"change_pct", "momentum_pct", "premium_pct", "volatility"}


def create_choropleth(
    summary_df: pd.DataFrame,
    value_col: str = "median_price_per_sqm",
    legend_name: str = "중위 m2당 가격 (만원/m2)",
    tooltip_data: pd.DataFrame = None,
) -> folium.Map:
    """구별 요약 데이터를 choropleth 지도로 시각화한다.

    Args:
        summary_df: gu_name, value_col 컬럼이 있는 DataFrame.
        value_col: 색상에 매핑할 값 컬럼.
        legend_name: 범례 이름.
        tooltip_data: 리치 툴팁에 표시할 종합 데이터 (gu_name + 5개 지표).

    Returns:
        folium.Map 객체.
    """
    geo_data = load_seoul_geo()

    # 색상 스케일 결정
    fill_color = _COLOR_SCALES["diverging"] if value_col in _DIVERGING_METRICS else _COLOR_SCALES["sequential"]

    m = folium.Map(
        location=[37.5665, 126.9780],
        zoom_start=11,
        tiles="cartodbpositron",
    )

    folium.Choropleth(
        geo_data=geo_data,
        data=summary_df,
        columns=["gu_name", value_col],
        key_on="feature.properties.SIG_KOR_NM",
        fill_color=fill_color,
        fill_opacity=0.8,
        line_opacity=0.4,
        legend_name=legend_name,
        nan_fill_color="#f8fafc",
    ).add_to(m)

    # 리치 툴팁 구성
    if tooltip_data is not None and not tooltip_data.empty:
        # GeoJSON feature에 데이터 주입
        tooltip_dict = {}
        for _, row in tooltip_data.iterrows():
            gu = row.get("gu_name", "")
            tooltip_dict[gu] = {
                "m2당가격": format_sqm_price(row.get("median_price_per_sqm", 0)),
                "중위가격": format_price(row.get("median_price", 0)),
                "상승률": format_pct(row.get("change_pct", 0)),
                "모멘텀": format_pct(row.get("momentum_pct", 0)),
                "변동성": format_pct(row.get("volatility", 0), with_sign=False),
                "프리미엄": format_pct(row.get("premium_pct", 0)),
                "거래건수": f"{int(row.get('trade_count', 0)):,}건",
            }

        def style_function(x):
            return {
                "fillColor": "transparent",
                "color": "transparent",
                "weight": 0,
            }

        def highlight_function(x):
            return {
                "fillColor": "transparent",
                "color": COLORS["primary"],
                "weight": 3,
            }

        # HTML 툴팁 생성
        for feature in geo_data["features"]:
            gu_name = feature["properties"].get("SIG_KOR_NM", "")
            data = tooltip_dict.get(gu_name, {})
            if data:
                html = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; min-width: 180px;">
                    <div style="font-weight: 700; font-size: 15px; margin-bottom: 6px; color: {COLORS['text_primary']};">{gu_name}</div>
                    <table style="border-collapse: collapse; width: 100%;">
                        <tr><td style="color: {COLORS['text_secondary']}; padding: 2px 8px 2px 0;">m2당</td><td style="font-weight: 600;">{data['m2당가격']}</td></tr>
                        <tr><td style="color: {COLORS['text_secondary']}; padding: 2px 8px 2px 0;">중위가격</td><td style="font-weight: 600;">{data['중위가격']}</td></tr>
                        <tr><td style="color: {COLORS['text_secondary']}; padding: 2px 8px 2px 0;">상승률</td><td style="font-weight: 600;">{data['상승률']}</td></tr>
                        <tr><td style="color: {COLORS['text_secondary']}; padding: 2px 8px 2px 0;">모멘텀</td><td style="font-weight: 600;">{data['모멘텀']}</td></tr>
                        <tr><td style="color: {COLORS['text_secondary']}; padding: 2px 8px 2px 0;">변동성</td><td style="font-weight: 600;">{data['변동성']}</td></tr>
                        <tr><td style="color: {COLORS['text_secondary']}; padding: 2px 8px 2px 0;">프리미엄</td><td style="font-weight: 600;">{data['프리미엄']}</td></tr>
                        <tr><td style="color: {COLORS['text_secondary']}; padding: 2px 8px 2px 0;">거래건수</td><td style="font-weight: 600;">{data['거래건수']}</td></tr>
                    </table>
                </div>
                """
                feature["properties"]["_tooltip_html"] = html
            else:
                feature["properties"]["_tooltip_html"] = f"<b>{gu_name}</b>"

        folium.GeoJson(
            geo_data,
            style_function=style_function,
            highlight_function=highlight_function,
            tooltip=folium.GeoJsonTooltip(
                fields=["_tooltip_html"],
                aliases=[""],
                labels=False,
                sticky=True,
                style=f"""
                    background-color: white;
                    border: 1px solid {COLORS['border']};
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.12);
                    padding: 12px;
                """,
                # parse_html=True를 folium이 지원하지 않으므로 fields에 HTML 포함
            ),
        ).add_to(m)
    else:
        # tooltip_data 없으면 기본 구 이름만
        style_function = lambda x: {
            "fillColor": "transparent",
            "color": "transparent",
            "weight": 0,
        }
        tooltip = folium.GeoJsonTooltip(fields=["SIG_KOR_NM"], aliases=["구"])
        folium.GeoJson(
            geo_data,
            style_function=style_function,
            tooltip=tooltip,
        ).add_to(m)

    return m

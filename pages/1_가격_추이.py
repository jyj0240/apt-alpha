"""가격 추이 — 답 먼저 + 전문가 접기 패턴 (개편 v1, docs/REDESIGN.md).

일반 사용자: 판정 카드 + 핵심 숫자 + 추이 차트 + 동별 비교.
전문가 모드(사이드바 토글): 랭킹·변동성 히트맵·동별 격차·원시 데이터 펼침.
"""

import streamlit as st

from data_pipeline import current_filters, load_trade
from data_processor import (
    aggregate_by_gu_month,
    aggregate_by_dong_month,
    calc_period_change,
    calc_recent_momentum,
    calc_relative_premium,
    calc_volatility,
    get_dong_gap_summary,
    generate_insight_text,
)
from design_system import (
    verdict_card, signal_from_metrics, hero_metrics, pro_section,
    show_chart, format_pct, calc_table_height,
)
from visualizer import (
    price_trend_chart,
    price_per_sqm_chart,
    trade_volume_chart,
    ranking_bar_chart,
    volatility_heatmap,
    dong_comparison_chart,
)
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()

f = current_filters()
selected_gus = f["gus"]
if not selected_gus:
    st.info("홈 또는 사이드바에서 관심 지역을 선택하세요.")
    st.stop()

df = load_trade(
    selected_gus, f["start_ym"], f["end_ym"],
    area=f["area"], build_year=f["build_year"],
    exclude_outliers=f["exclude_outliers"],
)
if df.empty:
    st.warning("해당 조건의 데이터가 없습니다.")
    st.stop()

gu_agg = aggregate_by_gu_month(df)

# --- 지표 계산 ---
change_df = calc_period_change(gu_agg)
momentum_df = calc_recent_momentum(gu_agg)
premium_df = calc_relative_premium(gu_agg)
vol_df = calc_volatility(gu_agg)

primary_gu = selected_gus[0]


def _val(metric_df, col):
    row = metric_df.loc[metric_df["gu_name"] == primary_gu, col]
    return float(row.iloc[0]) if not row.empty else 0.0


change_val = _val(change_df, "change_pct")
momentum_val = _val(momentum_df, "momentum_pct")
premium_val = _val(premium_df, "premium_pct")
vol_val = _val(vol_df, "volatility")

# --- 1층: 판정 카드 ---
gu_label = " / ".join(selected_gus)
st.markdown(f"### {gu_label}")

sig = signal_from_metrics(change_pct=change_val, momentum_pct=momentum_val)
headline = f"{primary_gu}는 지금 '{sig['label']}' 흐름입니다."
sub = generate_insight_text(primary_gu, change_val, momentum_val, premium_val, vol_val)
verdict_card(headline, sub=sub, signal=sig)

# --- 2층: 핵심 숫자 ---
hero_metrics([
    ("거래", f"{len(df):,}건"),
    ("기간 상승률", format_pct(change_val)),
    ("최근 상승세", format_pct(momentum_val)),
    ("서울 평균 대비", format_pct(premium_val)),
])

st.divider()

# --- 메인 차트 (일상: 실거래가 / m2당가 / 거래량) ---
t1, t2, t3 = st.tabs(["실거래가", "m2당가", "거래량"])
with t1:
    show_chart(price_trend_chart(gu_agg, selected_gus), key="c_trend")
with t2:
    show_chart(price_per_sqm_chart(gu_agg, selected_gus), key="c_sqm")
with t3:
    show_chart(trade_volume_chart(gu_agg, selected_gus), key="c_vol")

st.divider()

# --- 동별 비교 ---
st.markdown("#### 동별 비교")
dong_gu = st.selectbox("구", selected_gus, key="dong_gu", label_visibility="collapsed")
dong_agg = aggregate_by_dong_month(df)
show_chart(dong_comparison_chart(dong_agg, dong_gu), key="c_dong")

# --- 전문가 지표 (Pro 모드에서 펼침) ---
with pro_section("랭킹 · 변동성 · 상세 데이터"):
    pt1, pt2, pt3, pt4 = st.tabs(["상승률 랭킹", "변동성 히트맵", "동별 격차", "원시 데이터"])

    with pt1:
        if not change_df.empty:
            show_chart(
                ranking_bar_chart(change_df, "change_pct",
                                  title="구별 상승률 (%)", value_label="상승률 (%)"),
                key="c_rank")

    with pt2:
        show_chart(volatility_heatmap(gu_agg, selected_gus), key="c_heat")

    with pt3:
        gap_df = get_dong_gap_summary(df)
        if not gap_df.empty:
            st.dataframe(
                gap_df.rename(columns={
                    "gu_name": "구", "top_dong": "최고동", "top_price": "최고가",
                    "bottom_dong": "최저동", "bottom_price": "최저가", "gap": "격차",
                }),
                use_container_width=True, hide_index=True,
            )

    with pt4:
        cols = ["gu_name", "dong", "apt_name", "area", "floor", "price", "price_per_sqm", "date"]
        avail = [c for c in cols if c in df.columns]
        st.dataframe(
            df[avail].sort_values("date", ascending=False).head(300),
            use_container_width=True, hide_index=True,
            height=calc_table_height(min(len(df), 12)),
        )

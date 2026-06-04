import streamlit as st

from config import GU_NAME_TO_CODE
from data_collector import collect_seoul_data
from sidebar_filters import render_sidebar_filters
from data_processor import (
    clean_trade_data,
    add_area_category,
    filter_by_area,
    filter_by_build_year,
    filter_outliers,
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
    COLORS, CATEGORICAL_10, create_figure, format_price, format_pct,
    calc_table_height, show_chart,
)
from visualizer import (
    price_trend_chart,
    price_per_sqm_chart,
    trade_volume_chart,
    ranking_bar_chart,
    volatility_heatmap,
)
import plotly.graph_objects as go

render_sidebar_filters()

selected_gus = st.session_state.get("selected_gus", [])
start_ym = st.session_state.get("start_ym", "202401")
end_ym = st.session_state.get("end_ym", "202412")
selected_area = st.session_state.get("selected_area", "전체")
selected_build_year = st.session_state.get("selected_build_year", "전체")

if not selected_gus:
    st.info("홈에서 관심 지역을 선택하세요.")
    st.stop()

# --- 데이터 ---
@st.cache_data(show_spinner="데이터 수집 중...")
def get_data(gus, s_ym, e_ym):
    codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
    return collect_seoul_data(s_ym, e_ym, codes)

raw_df = get_data(selected_gus, start_ym, end_ym)
if raw_df.empty:
    st.warning("데이터가 없습니다.")
    st.stop()

df = clean_trade_data(raw_df)
df = add_area_category(df)
df = filter_by_area(df, selected_area)
df = filter_by_build_year(df, selected_build_year)
df = filter_outliers(df, st.session_state.get("exclude_outliers", True))

if df.empty:
    st.warning("해당 조건의 데이터가 없습니다.")
    st.stop()

gu_agg = aggregate_by_gu_month(df)

# --- KPI ---
change_df = calc_period_change(gu_agg)
momentum_df = calc_recent_momentum(gu_agg)
premium_df = calc_relative_premium(gu_agg)
vol_df = calc_volatility(gu_agg)

primary_gu = selected_gus[0]

def _get_val(metric_df, col, gu):
    row = metric_df.loc[metric_df["gu_name"] == gu, col]
    return row.iloc[0] if not row.empty else 0.0

change_val = _get_val(change_df, "change_pct", primary_gu)
momentum_val = _get_val(momentum_df, "momentum_pct", primary_gu)
premium_val = _get_val(premium_df, "premium_pct", primary_gu)
vol_val = _get_val(vol_df, "volatility", primary_gu)

# 헤더 + KPI 인라인
gu_label = " / ".join(selected_gus)
st.markdown(f"### {gu_label}")

k1, k2, k3, k4 = st.columns(4)
k1.metric("거래", f"{len(df):,}건")
k2.metric("상승률", f"{change_val:+.1f}%")
k3.metric("모멘텀", f"{momentum_val:+.1f}%")
k4.metric("프리미엄", f"{premium_val:+.1f}%")

# 인사이트
insight = generate_insight_text(primary_gu, change_val, momentum_val, premium_val, vol_val)
st.caption(insight)

st.divider()

# --- 메인 차트 (탭) ---
t1, t2, t3, t4, t5 = st.tabs(["실거래가", "m2당가", "거래량", "랭킹", "히트맵"])

with t1:
    show_chart(price_trend_chart(gu_agg, selected_gus),
                    use_container_width=True, key="c_trend")

with t2:
    show_chart(price_per_sqm_chart(gu_agg, selected_gus),
                    use_container_width=True, key="c_sqm")

with t3:
    show_chart(trade_volume_chart(gu_agg, selected_gus),
                    use_container_width=True, key="c_vol")

with t4:
    if not change_df.empty:
        show_chart(
            ranking_bar_chart(change_df, "change_pct",
                              title="구별 상승률 (%)", value_label="상승률 (%)"),
            use_container_width=True, key="c_rank")

with t5:
    show_chart(volatility_heatmap(gu_agg, selected_gus),
                    use_container_width=True, key="c_heat")

st.divider()

# --- 동별 비교 ---
st.markdown("#### 동별 비교")
dong_gu = st.selectbox("구", selected_gus, key="dong_gu", label_visibility="collapsed")
dong_agg = aggregate_by_dong_month(df)

# 동별 바차트를 직접 그리기 (visualizer 함수 대신 — 더 컴팩트)
from visualizer import dong_comparison_chart
show_chart(dong_comparison_chart(dong_agg, dong_gu),
                use_container_width=True, key="c_dong")

# --- 테이블 (expander) ---
with st.expander("상세 데이터"):
    tab_a, tab_b, tab_c = st.tabs(["변동성", "동별 격차", "원시 데이터"])

    with tab_a:
        if not vol_df.empty:
            st.dataframe(
                vol_df.rename(columns={"gu_name": "구", "volatility": "변동성%"}),
                use_container_width=True, hide_index=True,
            )

    with tab_b:
        gap_df = get_dong_gap_summary(df)
        if not gap_df.empty:
            st.dataframe(
                gap_df.rename(columns={
                    "gu_name": "구", "top_dong": "최고동", "top_price": "최고가",
                    "bottom_dong": "최저동", "bottom_price": "최저가", "gap": "격차",
                }),
                use_container_width=True, hide_index=True,
            )

    with tab_c:
        cols = ["gu_name", "dong", "apt_name", "area", "floor", "price", "price_per_sqm", "date"]
        avail = [c for c in cols if c in df.columns]
        st.dataframe(
            df[avail].sort_values("date", ascending=False).head(300),
            use_container_width=True, hide_index=True,
        )

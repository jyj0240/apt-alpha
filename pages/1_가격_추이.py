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
from design_system import calc_table_height
from visualizer import (
    price_trend_chart,
    price_per_sqm_chart,
    trade_volume_chart,
    area_price_scatter,
    dong_comparison_chart,
    ranking_bar_chart,
    volatility_heatmap,
)

render_sidebar_filters()
st.header("가격 추이 분석")

selected_gus = st.session_state.get("selected_gus", [])
start_ym = st.session_state.get("start_ym", "202401")
end_ym = st.session_state.get("end_ym", "202412")
selected_area = st.session_state.get("selected_area", "전체")
selected_build_year = st.session_state.get("selected_build_year", "전체")

if not selected_gus:
    st.info("사이드바에서 구를 선택하세요.")
    st.stop()

# 데이터 수집 (구+월 단위 자동 캐싱)
@st.cache_data(show_spinner="데이터 수집 중...")
def get_data(gus, s_ym, e_ym):
    gu_codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
    return collect_seoul_data(s_ym, e_ym, gu_codes)


raw_df = get_data(selected_gus, start_ym, end_ym)

if raw_df.empty:
    st.warning("조회된 데이터가 없습니다. 기간과 구를 확인하세요.")
    st.stop()

# 데이터 정제
df = clean_trade_data(raw_df)
df = add_area_category(df)
df = filter_by_area(df, selected_area)
df = filter_by_build_year(df, selected_build_year)
df = filter_outliers(df, st.session_state.get("exclude_outliers", True))

if df.empty:
    st.warning("해당 면적대 데이터가 없습니다.")
    st.stop()

# 집계
gu_agg = aggregate_by_gu_month(df)

# --- 상단 KPI 카드 ---
change_df = calc_period_change(gu_agg)
momentum_df = calc_recent_momentum(gu_agg)
premium_df = calc_relative_premium(gu_agg)
vol_df = calc_volatility(gu_agg)

# 선택된 구 중 첫번째 기준으로 KPI 표시
primary_gu = selected_gus[0]

change_val = change_df.loc[change_df["gu_name"] == primary_gu, "change_pct"]
change_val = change_val.iloc[0] if not change_val.empty else 0.0

momentum_val = momentum_df.loc[momentum_df["gu_name"] == primary_gu, "momentum_pct"]
momentum_val = momentum_val.iloc[0] if not momentum_val.empty else 0.0

premium_val = premium_df.loc[premium_df["gu_name"] == primary_gu, "premium_pct"]
premium_val = premium_val.iloc[0] if not premium_val.empty else 0.0

vol_val = vol_df.loc[vol_df["gu_name"] == primary_gu, "volatility"]
vol_val = vol_val.iloc[0] if not vol_val.empty else 0.0

kr1 = st.columns(2)
kr1[0].metric("총 거래 건수", f"{len(df):,}건")
kr1[1].metric(f"기간 상승률 ({primary_gu})", f"{change_val:+.1f}%")
kr2 = st.columns(2)
kr2[0].metric("최근 3개월 모멘텀", f"{momentum_val:+.1f}%")
kr2[1].metric("서울 평균 대비", f"{premium_val:+.1f}%")

# --- 자동 인사이트 (상단 배치) ---
st.markdown("<br>", unsafe_allow_html=True)
insight = generate_insight_text(primary_gu, change_val, momentum_val, premium_val, vol_val)
st.info(f"**{primary_gu} 분석 요약:** {insight}")

st.divider()

# --- 메인 차트 리포트 (탭 구조) ---
chart_tab1, chart_tab2, chart_tab3 = st.tabs(["중위 실거래가", "m2당 가격", "거래량"])

with chart_tab1:
    st.plotly_chart(price_trend_chart(gu_agg, selected_gus), use_container_width=True, key="chart_price_trend")

with chart_tab2:
    st.plotly_chart(price_per_sqm_chart(gu_agg, selected_gus), use_container_width=True, key="chart_price_per_sqm")

with chart_tab3:
    st.plotly_chart(trade_volume_chart(gu_agg, selected_gus), use_container_width=True, key="chart_trade_volume")

st.divider()

# --- 상세 분석 (Expander) ---
with st.expander("📊 상세 분석 (상승률 랭킹, 변동성 히트맵, 가격 분포)", expanded=False):
    st.subheader("구별 기간 상승률 랭킹")
    st.plotly_chart(
        ranking_bar_chart(change_df, "change_pct", title="서울 구별 상승률 (%)", value_label="상승률 (%)"),
        use_container_width=True,
        key="chart_ranking",
    )
    
    st.divider()
    st.subheader("구별 월간 변동성 히트맵")
    st.plotly_chart(volatility_heatmap(gu_agg, selected_gus), use_container_width=True, key="chart_heatmap")
    
    st.divider()
    st.subheader("전용면적 대비 가격 분포 (산점도)")
    st.plotly_chart(area_price_scatter(df), use_container_width=True, key="chart_scatter")

# --- 지역별 데이터 상세 ---
st.divider()
st.subheader("지역별 상세 지표")

lcol, rcol = st.columns(2)
with lcol:
    st.markdown("**구별 변동성 데이터**")
    if not vol_df.empty:
        _vol_display = vol_df.rename(columns={"gu_name": "구", "volatility": "변동성 (%)"})
        st.dataframe(
            _vol_display,
            use_container_width=True,
            hide_index=True,
            height=calc_table_height(len(_vol_display)),
        )

with rcol:
    st.markdown("**구 내 동별 가격 격차**")
    gap_df = get_dong_gap_summary(df)
    if not gap_df.empty:
        display_gap = gap_df.rename(columns={
            "gu_name": "구",
            "top_dong": "최고가 동",
            "top_price": "최고가",
            "bottom_dong": "최저가 동",
            "bottom_price": "최저가",
            "gap": "격차",
        })
        _gap_display = display_gap[["구", "최고가 동", "최고가", "최저가 동", "최저가", "격차"]]
        st.dataframe(_gap_display, use_container_width=True, hide_index=True, height=calc_table_height(len(_gap_display)))

# --- 동별 비교 ---
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("특정 구 내 동별 비교")
dong_gu = st.selectbox("조회할 구 선택", selected_gus)
dong_agg = aggregate_by_dong_month(df)
st.plotly_chart(dong_comparison_chart(dong_agg, dong_gu), use_container_width=True, key="chart_dong_comparison")

# 원시 데이터
with st.expander("🔍 전체 실거래 원시 데이터 (최신 500건)"):
    _raw = df[["gu_name", "dong", "apt_name", "area", "floor", "price", "price_per_sqm", "date"]].sort_values("date", ascending=False).head(500)
    st.dataframe(
        _raw,
        use_container_width=True,
        height=calc_table_height(len(_raw), max_h=600),
    )

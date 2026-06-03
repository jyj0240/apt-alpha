import streamlit as st
from streamlit_folium import st_folium

from data_collector import collect_seoul_data
from sidebar_filters import render_sidebar_filters
from data_processor import (
    clean_trade_data,
    filter_outliers,
    get_gu_summary,
    aggregate_by_gu_month,
    calc_period_change,
    calc_recent_momentum,
    calc_volatility,
    calc_relative_premium,
)
from map_view import create_choropleth

render_sidebar_filters()
st.header("서울 구별 지도")

start_ym = st.session_state.get("start_ym", "202401")
end_ym = st.session_state.get("end_ym", "202412")


# 지도는 서울 전체 25개 구 데이터 필요
@st.cache_data(show_spinner="서울 전체 데이터 수집 중...")
def get_all_data(s_ym, e_ym):
    return collect_seoul_data(s_ym, e_ym)


raw_df = get_all_data(start_ym, end_ym)

if raw_df.empty:
    st.warning("데이터가 없습니다.")
    st.stop()

df = clean_trade_data(raw_df)
df = filter_outliers(df, st.session_state.get("exclude_outliers", True))
gu_agg = aggregate_by_gu_month(df)
summary = get_gu_summary(df)

if summary.empty:
    st.warning("요약 데이터를 생성할 수 없습니다.")
    st.stop()

# 파생지표 merge
change_df = calc_period_change(gu_agg)
momentum_df = calc_recent_momentum(gu_agg)
vol_df = calc_volatility(gu_agg)
premium_df = calc_relative_premium(gu_agg)

summary = summary.merge(change_df, on="gu_name", how="left")
summary = summary.merge(momentum_df, on="gu_name", how="left")
summary = summary.merge(vol_df, on="gu_name", how="left")
summary = summary.merge(premium_df, on="gu_name", how="left")
summary = summary.fillna(0)

# 지표 선택 (5개)
metric = st.radio(
    "📊 지도에 표시할 지표를 선택하세요",
    ["m2당 가격", "거래량", "기간 상승률", "변동성", "서울 평균 대비 프리미엄"],
    horizontal=True,
)

col_map = {
    "m2당 가격": ("median_price_per_sqm", "중위 m2당 가격 (만원/m2)"),
    "거래량": ("trade_count", "거래 건수"),
    "기간 상승률": ("change_pct", "기간 상승률 (%)"),
    "변동성": ("volatility", "변동성 (%)"),
    "서울 평균 대비 프리미엄": ("premium_pct", "프리미엄 (%)"),
}

value_col, legend = col_map[metric]

# 지도 출력
st.markdown(f"### 서울 구별 {metric} 분포")
m = create_choropleth(summary, value_col=value_col, legend_name=legend, tooltip_data=summary)
st_folium(m, use_container_width=True, height=500)

# 요약 테이블
st.divider()
st.subheader("구별 종합 지표 리포트")
display_df = summary.sort_values(value_col, ascending=False)

from design_system import calc_table_height
_map_tbl = display_df[["gu_name", "median_price_per_sqm", "change_pct", "momentum_pct", "volatility", "premium_pct", "trade_count"]]
st.dataframe(
    _map_tbl,
    column_config={
        "gu_name": st.column_config.TextColumn("구"),
        "median_price_per_sqm": st.column_config.NumberColumn("m2당(만원/m2)", format="%,.1f"),
        "change_pct": st.column_config.NumberColumn("상승률(%)", format="%+.1f"),
        "momentum_pct": st.column_config.NumberColumn("3개월모멘텀(%)", format="%+.1f"),
        "volatility": st.column_config.NumberColumn("변동성(%)", format="%.1f"),
        "premium_pct": st.column_config.NumberColumn("프리미엄(%)", format="%+.1f"),
        "trade_count": st.column_config.NumberColumn("거래건수", format="%d건"),
    },
    use_container_width=True,
    hide_index=True,
    height=calc_table_height(len(_map_tbl)),
)

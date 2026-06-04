import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from config import GU_NAME_TO_CODE
from data_collector import collect_seoul_data, collect_seoul_rent_data
from data_processor import (
    clean_trade_data, clean_rent_data,
    add_area_category, filter_outliers,
)
from screener import screen_complexes
from design_system import (
    COLORS, CATEGORICAL_10, apply_theme, create_figure,
    format_price, format_sqm_price, format_pct, calc_table_height,
)
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()
st.header("스크리닝")

st.markdown("""
조건에 맞는 아파트 단지를 **5가지 팩터로 스코어링**하여 랭킹합니다.
주식 퀀트 스크리닝과 동일한 개념 -- "어떤 단지가 지금 매력적인가?"를 데이터로 판단합니다.

| 팩터 | 의미 | 높으면 |
|------|------|--------|
| **Momentum** | 최근 N개월 가격 상승률 | 오르는 추세 |
| **Value** | 같은 구 동급 대비 상대적 가격 (낮으면 고점수) | 저평가 가능 |
| **Alpha** | 구 평균 대비 초과 수익률 | 구조적 우위 |
| **Liquidity** | 월평균 거래 빈도 | 사고팔기 쉬움 |
| **Safety** | 전세가율 높고 변동성 낮음 | 하방 리스크 낮음 |
""")

st.divider()

# --- 스크리닝 조건 ---
selected_gus = st.session_state.get("selected_gus", [])
start_ym = st.session_state.get("start_ym", "202401")
end_ym = st.session_state.get("end_ym", "202412")

if not selected_gus:
    st.info("사이드바에서 분석할 구를 선택하세요. (서초구, 강남구 등)")
    st.stop()

# 스크리닝 파라미터
st.subheader("스크리닝 조건")
sp1 = st.columns(2)
target_area = sp1[0].selectbox("타겟 면적", [59, 84, 85, 102, 114, 135], index=2,
                               format_func=lambda x: f"{x}m2")
area_tol = sp1[1].selectbox("허용 오차", [3, 5, 10], index=1,
                            format_func=lambda x: f"+-{x}m2")

cur_year = datetime.today().year
build_options = {
    "전체": (0, cur_year + 1),
    "신축 (5년 이내)": (cur_year - 5, cur_year + 1),
    "준신축 (5~10년)": (cur_year - 10, cur_year - 5),
    "중축 (10~20년)": (cur_year - 20, cur_year - 10),
    "구축 (20년+)": (0, cur_year - 20),
}
sp2 = st.columns(2)
build_filter = sp2[0].selectbox("연식", list(build_options.keys()), index=2)
months_mom = sp2[1].selectbox("모멘텀 기간", [3, 6, 12], index=1,
                              format_func=lambda x: f"최근 {x}개월")

min_trades = st.slider("최소 거래건수", min_value=3, max_value=30, value=5,
                       help="거래가 너무 적은 단지는 통계적으로 신뢰하기 어렵습니다.")

# --- 데이터 로드 ---
@st.cache_data(show_spinner="데이터 수집 중...")
def get_data(gus, s_ym, e_ym):
    codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
    return collect_seoul_data(s_ym, e_ym, codes)

@st.cache_data(show_spinner="전월세 데이터 수집 중...")
def get_rent(gus, s_ym, e_ym):
    codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
    return collect_seoul_rent_data(s_ym, e_ym, codes)

raw_trade = get_data(tuple(selected_gus), start_ym, end_ym)
if raw_trade.empty:
    st.warning("매매 데이터가 없습니다.")
    st.stop()

df_trade = clean_trade_data(raw_trade)
df_trade = add_area_category(df_trade)
df_trade = filter_outliers(df_trade, st.session_state.get("exclude_outliers", True))

# 연식 필터
build_lo, build_hi = build_options[build_filter]
if build_filter != "전체":
    df_trade = df_trade[df_trade["build_year"].between(build_lo, build_hi - 1)]

# 전월세 데이터 (가능하면)
rent_clean = None
try:
    raw_rent = get_rent(tuple(selected_gus), start_ym, end_ym)
    if not raw_rent.empty:
        rent_clean = clean_rent_data(raw_rent)
except Exception:
    pass

if df_trade.empty:
    st.warning("해당 조건의 데이터가 없습니다.")
    st.stop()

# --- 스크리닝 실행 ---
with st.spinner("스크리닝 중..."):
    screened = screen_complexes(
        df_trade, rent_clean,
        target_area=target_area,
        area_tolerance=area_tol,
        min_trades=min_trades,
        months_momentum=months_mom,
    )

if screened.empty:
    st.warning("조건에 맞는 단지가 없습니다. 조건을 완화해 보세요.")
    st.stop()

# --- 결과 표시 ---
st.divider()

gu_label = " / ".join(selected_gus)
st.subheader(f"스크리닝 결과: {gu_label} {target_area}m2 ({build_filter})")
st.caption(f"총 {len(screened)}개 단지 분석 완료 / 모멘텀 {months_mom}개월 기준")

# --- Top 10 종합 ---
top_n = min(10, len(screened))
top = screened.head(top_n)

# KPI
k1, k2, k3 = st.columns(3)
k1.metric("1위", f"{top.iloc[0]['apt_name']}", delta=f"종합 {top.iloc[0]['score_total']:.0f}점")
if len(top) > 1:
    k2.metric("2위", f"{top.iloc[1]['apt_name']}", delta=f"종합 {top.iloc[1]['score_total']:.0f}점")
if len(top) > 2:
    k3.metric("3위", f"{top.iloc[2]['apt_name']}", delta=f"종합 {top.iloc[2]['score_total']:.0f}점")

st.divider()

tab1, tab2, tab3 = st.tabs(["종합 랭킹", "팩터별 비교", "상세 테이블"])

# === Tab 1: 종합 랭킹 ===
with tab1:
    top_sorted = top.sort_values("score_total")
    labels = top_sorted["apt_name"] + " (" + top_sorted["dong"] + ")"

    fig = create_figure(
        title=f"Top {top_n} 종합 스코어",
        xaxis_title="종합 점수", yaxis_title="",
        height=max(300, top_n * 40),
    )

    # 스택 바: 각 팩터 기여분
    score_cols = [
        ("score_momentum", "Momentum", COLORS["primary"]),
        ("score_value", "Value", COLORS["up"]),
        ("score_alpha", "Alpha", COLORS["accent"]),
        ("score_liquidity", "Liquidity", COLORS["warning"]),
        ("score_safety", "Safety", "#0891b2"),
    ]
    weights = [0.30, 0.20, 0.20, 0.15, 0.15]

    for (col, name, color), w in zip(score_cols, weights):
        fig.add_trace(go.Bar(
            x=top_sorted[col] * w,
            y=labels,
            orientation="h",
            name=name,
            marker_color=color,
            hovertemplate=f"{name}: " + "%{customdata:.0f}점<extra></extra>",
            customdata=top_sorted[col],
        ))

    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig, use_container_width=True, key="chart_screen_total")

    st.markdown("""
    **읽는 법**: 막대 전체 길이 = 종합 점수. 색상별로 어떤 팩터에서 점수를 얻었는지 보입니다.
    파란색(Momentum)이 크면 상승 추세가 강하고, 초록(Value)이 크면 상대적으로 저평가입니다.
    """)

# === Tab 2: 팩터별 비교 ===
with tab2:
    st.subheader("팩터별 Top 5")

    factor_tabs = st.tabs(["Momentum", "Value", "Alpha", "Liquidity", "Safety"])

    factor_configs = [
        ("score_momentum", "momentum_pct", "상승률(%)", "Momentum: 최근 가격 상승 추세가 강한 단지", COLORS["primary"]),
        ("score_value", "median_sqm", "m2당가(만원)", "Value: 같은 구 동급 대비 상대적으로 저평가된 단지", COLORS["up"]),
        ("score_alpha", "alpha_pct", "초과수익률(%)", "Alpha: 구 평균보다 더 잘 오른(고유 가치가 있는) 단지", COLORS["accent"]),
        ("score_liquidity", "monthly_trades", "월평균 거래(건)", "Liquidity: 거래가 활발해 매도 시 유리한 단지", COLORS["warning"]),
        ("score_safety", "jeonse_ratio", "전세가율(%)", "Safety: 전세가율 높고 변동성 낮아 하방 리스크가 적은 단지", "#0891b2"),
    ]

    for tab, (score_col, raw_col, raw_label, desc, color) in zip(factor_tabs, factor_configs):
        with tab:
            st.caption(desc)
            top5 = screened.nlargest(5, score_col)
            top5_sorted = top5.sort_values(score_col)

            fig_f = create_figure(
                xaxis_title=raw_label, yaxis_title="",
                height=250,
            )
            fig_f.add_trace(go.Bar(
                x=top5_sorted[raw_col],
                y=top5_sorted["apt_name"] + " (" + top5_sorted["dong"] + ")",
                orientation="h",
                marker_color=color,
                text=[f"{v:.1f}" for v in top5_sorted[raw_col]],
                textposition="outside",
            ))
            st.plotly_chart(fig_f, use_container_width=True, key=f"chart_factor_{score_col}")

# === Tab 3: 상세 테이블 ===
with tab3:
    st.subheader("전체 스크리닝 결과")

    display = screened[[
        "gu_name", "dong", "apt_name", "build_year",
        "median_sqm", "median_price", "total_trades",
        "momentum_pct", "alpha_pct", "monthly_trades", "jeonse_ratio", "volatility",
        "score_momentum", "score_value", "score_alpha", "score_liquidity", "score_safety",
        "score_total",
    ]].copy()

    display = display.rename(columns={
        "gu_name": "구", "dong": "동", "apt_name": "단지",
        "build_year": "건축", "median_sqm": "m2당가",
        "median_price": "중위가(만원)", "total_trades": "거래수",
        "momentum_pct": "모멘텀(%)", "alpha_pct": "알파(%)",
        "monthly_trades": "월거래", "jeonse_ratio": "전세가율",
        "volatility": "변동성",
        "score_momentum": "S.Mom", "score_value": "S.Val",
        "score_alpha": "S.Alp", "score_liquidity": "S.Liq",
        "score_safety": "S.Saf", "score_total": "종합",
    })

    st.dataframe(
        display,
        column_config={
            "m2당가": st.column_config.NumberColumn(format="%.1f"),
            "중위가(만원)": st.column_config.NumberColumn(format="%,d"),
            "모멘텀(%)": st.column_config.NumberColumn(format="%+.1f"),
            "알파(%)": st.column_config.NumberColumn(format="%+.1f"),
            "전세가율": st.column_config.NumberColumn(format="%.1f%%"),
            "변동성": st.column_config.NumberColumn(format="%.2f"),
            "종합": st.column_config.NumberColumn(format="%.0f"),
        },
        use_container_width=True,
        hide_index=True,
        height=calc_table_height(len(display)),
    )

    st.caption("""
    **스코어 가중치**: Momentum 30% / Value 20% / Alpha 20% / Liquidity 15% / Safety 15%
    """)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import GU_NAME_TO_CODE
from data_collector import collect_seoul_data, collect_seoul_rent_data
from data_processor import (
    clean_trade_data,
    clean_rent_data,
    filter_by_area,
    filter_by_build_year,
    add_area_category,
    aggregate_by_gu_month,
    aggregate_rent_by_gu_month,
    calc_jeonse_ratio,
    calc_period_change,
    calc_rent_escalation,
    calc_contract_type_ratio,
)
from visualizer import scatter_matrix_chart, ranking_bar_chart
from design_system import (
    COLORS, CATEGORICAL_10, apply_theme, create_figure,
    format_price, format_pct, calc_table_height,
)
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()
st.header("전월세 분석")

selected_gus = st.session_state.get("selected_gus", [])
start_ym = st.session_state.get("start_ym", "202401")
end_ym = st.session_state.get("end_ym", "202412")
selected_area = st.session_state.get("selected_area", "전체")

if not selected_gus:
    st.info("사이드바에서 구를 선택하세요.")
    st.stop()

gu_codes = [GU_NAME_TO_CODE[g] for g in selected_gus if g in GU_NAME_TO_CODE]


# --- 전월세 데이터 수집 ---
@st.cache_data(show_spinner="전월세 데이터 수집 중...")
def get_rent_data(gus, s_ym, e_ym):
    codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
    return collect_seoul_rent_data(s_ym, e_ym, codes)


raw_rent = get_rent_data(selected_gus, start_ym, end_ym)

if raw_rent.empty:
    st.warning(
        "전월세 데이터가 없습니다.\n\n"
        "전월세 API 활용신청이 필요할 수 있습니다:\n"
        "https://www.data.go.kr/data/15126474/openapi.do"
    )
    st.stop()

selected_build_year = st.session_state.get("selected_build_year", "전체")

rent_df = clean_rent_data(raw_rent)
rent_df = add_area_category(rent_df)
rent_df = filter_by_area(rent_df, selected_area)
rent_df = filter_by_build_year(rent_df, selected_build_year)

if rent_df.empty:
    st.warning("해당 조건의 전월세 데이터가 없습니다.")
    st.stop()

# --- 상단 KPI 카드 ---
jeonse_df = rent_df[rent_df["rent_type"] == "전세"]
wolse_df = rent_df[rent_df["rent_type"] == "월세"]
jeonse_ratio_val = len(jeonse_df) / len(rent_df) * 100 if len(rent_df) > 0 else 0

# 면적당 월세
wolse_per_area = (wolse_df["monthly_rent"] / wolse_df["area"]).median() if not wolse_df.empty else 0

# 전세가율 계산 (매매 데이터 필요)
trade_raw = collect_seoul_data(start_ym, end_ym, gu_codes)
avg_jeonse_ratio = None
jeonse_ratio_change = None
ratio_df = None
trade_agg = None

if not trade_raw.empty:
    trade_df = clean_trade_data(trade_raw)
    trade_df = filter_by_area(trade_df, selected_area)
    trade_agg = aggregate_by_gu_month(trade_df)
    rent_agg = aggregate_rent_by_gu_month(rent_df)
    ratio_df = calc_jeonse_ratio(trade_agg, rent_agg)

    if not ratio_df.empty:
        avg_jeonse_ratio = ratio_df["jeonse_ratio"].mean()
        # 전세가율 변화폭: 첫 달 vs 마지막 달
        first_ym = ratio_df["ym"].min()
        last_ym = ratio_df["ym"].max()
        first_avg = ratio_df[ratio_df["ym"] == first_ym]["jeonse_ratio"].mean()
        last_avg = ratio_df[ratio_df["ym"] == last_ym]["jeonse_ratio"].mean()
        jeonse_ratio_change = last_avg - first_avg

rr1 = st.columns(2)
rr1[0].metric("전세 비중", f"{jeonse_ratio_val:.0f}%")
rr1[1].metric("평균 전세가율", f"{avg_jeonse_ratio:.1f}%" if avg_jeonse_ratio else "N/A")
rr2 = st.columns(2)
rr2[0].metric("전세가율 변화", f"{jeonse_ratio_change:+.1f}%p" if jeonse_ratio_change else "N/A")
rr2[1].metric("월세 중위", f"{wolse_per_area:.1f}만원/m2" if wolse_per_area else "N/A")

st.divider()

# --- 1. 투자 매트릭스 & 전세가율 (가장 중요) ---
st.subheader("1. 매매 상승률 vs 전세가율 분석")
st.markdown("💡 **X축**: 매매 상승률 / **Y축**: 전세가율 → 사분면을 통해 투자 유망/주의 지역을 판단합니다.")

if not trade_raw.empty and ratio_df is not None and not ratio_df.empty:
    trade_change = calc_period_change(trade_agg)
    latest_ym = ratio_df["ym"].max()
    latest_ratio = ratio_df[ratio_df["ym"] == latest_ym][["gu_name", "jeonse_ratio"]]
    matrix_df = trade_change.merge(latest_ratio, on="gu_name", how="inner")

    if not matrix_df.empty:
        m_col1, m_col2 = st.columns([2, 1])
        with m_col1:
            fig = scatter_matrix_chart(
                matrix_df,
                x_col="change_pct",
                y_col="jeonse_ratio",
                title="매매 상승률 vs 전세가율 (구별)",
                x_label="매매 상승률 (%)",
                y_label="전세가율 (%)",
            )
            st.plotly_chart(fig, use_container_width=True, key="chart_matrix")
        
        with m_col2:
            st.markdown("""
            **사분면 해석**
            - **우상 (High-High)**: 상승세 + 전세 부담 큼
            - **좌상 (Low-High)**: 하락/보합 + 전세 높음 (저평가 가능)
            - **우하 (High-Low)**: 상승 + 전세 낮음 (갭투자 부담)
            - **좌하 (Low-Low)**: 시장 약세
            """)
            st.plotly_chart(
                ranking_bar_chart(
                    latest_ratio, "jeonse_ratio", title="구별 전세가율 (%)",
                    value_label="전세가율 (%)"
                ),
                use_container_width=True,
                key="chart_jeonse_ranking",
            )
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("2. 구별 월별 전세가율 추이")
    fig_r = px.line(
        ratio_df.sort_values("ym"),
        x="ym", y="jeonse_ratio", color="gu_name",
        title="구별 월별 전세가율 (%)",
        labels={"ym": "년월", "jeonse_ratio": "전세가율 (%)", "gu_name": "구"},
    )
    fig_r.update_layout(hovermode="x unified", xaxis_tickangle=-45)
    fig_r.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="70% 과열 기준")
    st.plotly_chart(fig_r, use_container_width=True, key="chart_jeonse_ratio")
else:
    st.info("매매 데이터와 전월세 데이터가 모두 필요합니다.")

st.divider()

# --- 2. 임대차 추이 (전세/월세) ---
rent_agg_all = aggregate_rent_by_gu_month(rent_df)

lcol, rcol = st.columns(2)

with lcol:
    st.subheader("3. 전세 보증금 추이")
    jeonse_agg = rent_agg_all[rent_agg_all["rent_type"] == "전세"]
    if not jeonse_agg.empty:
        fig_j = create_figure(
            title="중위 전세 보증금",
            xaxis_title="년월", yaxis_title="보증금 (만원)",
            hovermode="x unified", xaxis_tickangle=-45,
        )
        gu_list = sorted(jeonse_agg["gu_name"].unique())
        for i, gu in enumerate(gu_list):
            gu_d = jeonse_agg[jeonse_agg["gu_name"] == gu].sort_values("ym")
            color = CATEGORICAL_10[i % len(CATEGORICAL_10)]
            formatted = [format_price(p) for p in gu_d["median_deposit"]]
            fig_j.add_trace(go.Scatter(
                x=gu_d["ym"], y=gu_d["median_deposit"],
                name=gu, mode="lines+markers",
                line=dict(color=color, width=2), marker=dict(size=4),
                customdata=list(zip([gu] * len(gu_d), formatted)),
                hovertemplate="<b>%{customdata[0]}</b><br>%{x}<br>%{customdata[1]}<extra></extra>",
            ))
        st.plotly_chart(fig_j, use_container_width=True, key="chart_jeonse_deposit")
    else:
        st.info("전세 데이터 부족")

with rcol:
    st.subheader("4. 월세 가격 추이")
    wolse_agg = rent_agg_all[rent_agg_all["rent_type"] == "월세"]
    if not wolse_agg.empty:
        fig_w = create_figure(
            title="중위 월세",
            xaxis_title="년월", yaxis_title="월세 (만원)",
            hovermode="x unified", xaxis_tickangle=-45,
        )
        gu_list_w = sorted(wolse_agg["gu_name"].unique())
        for i, gu in enumerate(gu_list_w):
            gu_d = wolse_agg[wolse_agg["gu_name"] == gu].sort_values("ym")
            color = CATEGORICAL_10[i % len(CATEGORICAL_10)]
            fig_w.add_trace(go.Scatter(
                x=gu_d["ym"], y=gu_d["median_monthly_rent"],
                name=gu, mode="lines+markers",
                line=dict(color=color, width=2), marker=dict(size=4),
                customdata=[[gu]] * len(gu_d),
                hovertemplate="<b>%{customdata[0]}</b><br>%{x}<br>%{y:.0f}만원<extra></extra>",
            ))
        st.plotly_chart(fig_w, use_container_width=True, key="chart_wolse_rent")
    else:
        st.info("월세 데이터 부족")

st.divider()

# --- 3. 보증금 인상률 & 계약 유형 분석 ---
esc_col, ct_col = st.columns(2)

with esc_col:
    st.subheader("5. 갱신 계약 보증금 인상률")
    st.caption("이전 보증금 대비 갱신 시 인상률 (prev_deposit 데이터 기반)")
    esc_df = calc_rent_escalation(rent_df)
    if not esc_df.empty:
        esc_sorted = esc_df.sort_values("median_escalation_pct")
        fig_esc = create_figure(
            title="구별 갱신 보증금 인상률 (중위)",
            xaxis_title="인상률 (%)", yaxis_title="",
            height=max(300, len(esc_sorted) * 28),
        )
        esc_colors = [
            COLORS["down"] if v > 5 else (COLORS["warning"] if v > 0 else COLORS["up"])
            for v in esc_sorted["median_escalation_pct"]
        ]
        fig_esc.add_trace(go.Bar(
            x=esc_sorted["median_escalation_pct"],
            y=esc_sorted["gu_name"],
            orientation="h",
            marker_color=esc_colors,
            text=[f"{v:+.1f}%" for v in esc_sorted["median_escalation_pct"]],
            textposition="outside",
        ))
        st.plotly_chart(fig_esc, use_container_width=True, key="chart_rent_escalation")
    else:
        st.info("갱신 계약 데이터가 없습니다.")

with ct_col:
    st.subheader("6. 신규/갱신 계약 비율")
    st.caption("contract_type 기반 신규 vs 갱신 비율")
    ct_df = calc_contract_type_ratio(rent_df)
    if not ct_df.empty:
        ct_sorted = ct_df.sort_values("renewal_pct")
        fig_ct = create_figure(
            title="구별 갱신 계약 비율",
            xaxis_title="갱신 비율 (%)", yaxis_title="",
            height=max(300, len(ct_sorted) * 28),
        )
        fig_ct.add_trace(go.Bar(
            x=ct_sorted["renewal_pct"],
            y=ct_sorted["gu_name"],
            orientation="h",
            marker_color=COLORS["primary"],
            text=[f"{v:.1f}%" for v in ct_sorted["renewal_pct"]],
            textposition="outside",
            customdata=list(zip(ct_sorted["renewal_count"], ct_sorted["new_count"])),
            hovertemplate="<b>%{y}</b><br>갱신: %{customdata[0]}건<br>신규: %{customdata[1]}건<extra></extra>",
        ))
        st.plotly_chart(fig_ct, use_container_width=True, key="chart_contract_type")
    else:
        st.info("계약 유형 데이터가 없습니다.")

# 원시 데이터
with st.expander("전월세 실거래 원시 데이터 보기"):
    display_cols = ["gu_name", "dong", "apt_name", "area", "floor", "rent_type", "deposit", "monthly_rent", "date"]
    available_cols = [c for c in display_cols if c in rent_df.columns]
    _rent_raw = rent_df[available_cols].sort_values("date", ascending=False).head(500)
    st.dataframe(
        _rent_raw,
        use_container_width=True,
        height=calc_table_height(len(_rent_raw), max_h=600),
    )

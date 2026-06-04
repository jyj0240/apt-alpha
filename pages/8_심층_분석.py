import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

from config import GU_NAME_TO_CODE
from data_collector import collect_seoul_data, collect_seoul_rent_data
from data_processor import (
    clean_trade_data,
    clean_rent_data,
    add_area_category,
    filter_by_area,
    filter_by_build_year,
    filter_outliers,
    get_apt_price_history,
    aggregate_rent_by_gu_month,
    calc_jeonse_ratio,
    aggregate_by_gu_month,
    decompose_price_series,
    calc_rolling_volatility,
    calc_max_drawdown,
    calc_liquidity_score,
    find_comparable_complexes,
    calc_investment_score,
)
from design_system import (
    COLORS, CATEGORICAL_10, apply_theme, create_figure,
    format_price, format_pct, calc_table_height,
)
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()
st.header("심층 분석")

selected_gus = st.session_state.get("selected_gus", [])
start_ym = st.session_state.get("start_ym", "202401")
end_ym = st.session_state.get("end_ym", "202412")
selected_area = st.session_state.get("selected_area", "전체")
selected_build_year = st.session_state.get("selected_build_year", "전체")

if not selected_gus:
    st.info("사이드바에서 구를 선택하세요.")
    st.stop()


@st.cache_data(show_spinner="데이터 수집 중...")
def get_data(gus, s_ym, e_ym):
    codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
    return collect_seoul_data(s_ym, e_ym, codes)


raw_df = get_data(tuple(selected_gus), start_ym, end_ym)
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

# --- 단지 선택 ---
ds1 = st.columns(2)
with ds1[0]:
    gu_options = sorted(df["gu_name"].dropna().unique())
    selected_gu = st.selectbox("구", gu_options, key="deep_gu")
df_gu = df[df["gu_name"] == selected_gu]

with ds1[1]:
    dong_options = ["전체"] + sorted(df_gu["dong"].dropna().unique())
    selected_dong = st.selectbox("동", dong_options, key="deep_dong")
df_dong = df_gu if selected_dong == "전체" else df_gu[df_gu["dong"] == selected_dong]

ds2 = st.columns(2)
with ds2[0]:
    apt_counts = df_dong["apt_name"].value_counts()
    selected_apt = st.selectbox("단지", apt_counts.index.tolist(), key="deep_apt")
df_apt_all = df_dong[df_dong["apt_name"] == selected_apt]

with ds2[1]:
    if not df_apt_all.empty:
        areas = df_apt_all["area"].dropna().round(0).astype(int)
        area_counts = areas.value_counts().sort_index()
        area_labels = {0: "전체"}
        for a in area_counts.index:
            area_labels[a] = f"{a}m2 ({area_counts[a]}건)"
        area_keys = [0] + list(area_counts.index)
        apt_area = st.selectbox("전용면적", area_keys,
                                format_func=lambda x: area_labels.get(x, str(x)),
                                key="deep_area")
    else:
        apt_area = 0

if apt_area == 0:
    df_apt = df_apt_all
else:
    df_apt = df_apt_all[df_apt_all["area"].round(0).astype(int) == apt_area]

if df_apt.empty:
    st.warning("해당 조건의 거래 데이터가 없습니다.")
    st.stop()

# --- 기본 데이터 준비 ---
history = get_apt_price_history(df_apt, selected_apt)
build_year = int(df_apt["build_year"].median()) if df_apt["build_year"].notna().any() else 0
target_area = df_apt["area"].median()

st.divider()

# --- 4개 탭 ---
tab1, tab2, tab3, tab4 = st.tabs(["시계열 분해", "리스크", "비교 단지", "스코어카드"])

# =====================================================
# Tab 1: 시계열 분해
# =====================================================
with tab1:
    st.subheader("시계열 분해")
    st.markdown("""
    아파트 가격은 **장기 추세**(오르는지 내리는지), **계절 패턴**(봄/가을 거래 성수기),
    **노이즈**(일시적 변동)가 섞여 있습니다. 이 분석은 세 요소를 분리해서 보여줍니다.
    - **추세(Trend)**: 단기 등락을 제거한 실제 방향. 이것만 보면 진짜 오르는지 내리는지 알 수 있습니다
    - **계절성(Seasonal)**: 매년 반복되는 패턴. 어느 달에 비싸고 싼지 파악
    - **잔차(Residual)**: 추세도 계절도 아닌 비정상 변동. 급매나 이상 거래가 여기 나타납니다
    """)

    decomp = decompose_price_series(history)

    if decomp is None:
        st.info(f"시계열 분해에 최소 14개월 데이터가 필요합니다. (현재 {len(history)}개월)")
    else:
        # 4-panel 차트
        from plotly.subplots import make_subplots

        panels = ["원본 가격", "추세 (Trend)", "계절성 (Seasonal)", "잔차 (Residual)"]
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, subplot_titles=panels,
                            vertical_spacing=0.06)

        x_vals = [str(p) for p in decomp["observed"].index]

        fig.add_trace(go.Scatter(
            x=x_vals, y=decomp["observed"].values,
            mode="lines+markers", name="원본",
            line=dict(color=COLORS["neutral"], width=1), marker=dict(size=3),
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=x_vals, y=decomp["trend"].values,
            mode="lines", name="추세",
            line=dict(color=COLORS["primary"], width=2.5),
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=x_vals, y=decomp["seasonal"].values,
            mode="lines", name="계절성",
            line=dict(color=COLORS["accent"], width=1.5),
            fill="tozeroy", fillcolor="rgba(124,58,237,0.08)",
        ), row=3, col=1)

        fig.add_trace(go.Scatter(
            x=x_vals, y=decomp["resid"].values,
            mode="markers", name="잔차",
            marker=dict(color=COLORS["neutral"], size=4),
        ), row=4, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="#cbd5e1", row=4, col=1)

        fig.update_layout(
            height=520, showlegend=False,
            margin=dict(l=50, r=20, t=40, b=30),
        )
        apply_theme(fig)
        st.plotly_chart(fig, use_container_width=True, key="chart_decomp")

        # 해석 텍스트
        trend = decomp["trend"].dropna()
        if len(trend) >= 6:
            recent_trend = trend.iloc[-1] - trend.iloc[-6]
            trend_dir = "상승" if recent_trend > 0 else ("하락" if recent_trend < 0 else "보합")
            st.info(f"최근 6개월 추세: **{trend_dir}** ({format_price(abs(recent_trend))} {'상승' if recent_trend > 0 else '하락'})")

        seasonal = decomp["seasonal"]
        if len(seasonal) >= 12:
            monthly_avg = seasonal.groupby(seasonal.index.month).mean()
            best_month = monthly_avg.idxmax()
            worst_month = monthly_avg.idxmin()
            st.caption(f"계절 패턴: {best_month}월에 가장 높고, {worst_month}월에 가장 낮은 경향")


# =====================================================
# Tab 2: 리스크 대시보드
# =====================================================
with tab2:
    st.subheader("리스크 대시보드")
    st.markdown("""
    이 단지에 투자했을 때의 **위험 요소**를 정량적으로 보여줍니다.
    - **변동성**: 가격이 얼마나 출렁이는지. 높을수록 예측이 어렵고 리스크가 큼
    - **최대 낙폭(MDD)**: 과거 최고가에서 최대 얼마나 떨어졌는지. 최악의 시나리오 가늠
    - **유동성**: 거래가 얼마나 활발한지. 낮으면 팔고 싶을 때 못 팔 수 있음
    - **직거래 비율**: 중개사 없이 직접 거래한 비율. 높으면 가족 간 거래(시세보다 싸게)가 많을 수 있음
    """)

    # 지표 계산
    vol_df = calc_rolling_volatility(history)
    mdd = calc_max_drawdown(history)
    liq = calc_liquidity_score(df_apt, df_dong)

    # 직거래 비율
    direct_pct = 0.0
    if "trade_type" in df_apt.columns:
        direct = df_apt["trade_type"].astype(str).str.contains("직거래", na=False).sum()
        direct_pct = round(direct / len(df_apt) * 100, 1) if len(df_apt) > 0 else 0

    # 최근 12개월 변동성
    recent_vol = 0.0
    if not vol_df.empty and "vol_6m" in vol_df.columns:
        recent_vol = vol_df["vol_6m"].iloc[-1] if not pd.isna(vol_df["vol_6m"].iloc[-1]) else 0

    # KPI
    r1 = st.columns(4)
    r1[0].metric("변동성 (6개월)", f"{recent_vol:.2f}%")
    r1[1].metric("최대 낙폭 (MDD)", f"{mdd['mdd_pct']:+.1f}%",
                 delta=f"{mdd['peak_ym']} ~ {mdd['trough_ym']}", delta_color="off")
    r1[2].metric("유동성 (동 대비)", f"{liq['liquidity_ratio']:.2f}x",
                 delta=f"월평균 {liq['apt_monthly_avg']:.1f}건", delta_color="off")
    r1[3].metric("직거래 비율", f"{direct_pct:.1f}%")

    st.divider()

    # 롤링 변동성 차트
    if not vol_df.empty:
        fig_vol = create_figure(
            title="롤링 변동성 추이",
            xaxis_title="년월", yaxis_title="변동성 (%)",
            xaxis_tickangle=-45,
        )
        if "vol_3m" in vol_df.columns:
            fig_vol.add_trace(go.Scatter(
                x=vol_df["ym"], y=vol_df["vol_3m"],
                mode="lines", name="3개월",
                line=dict(color=COLORS["warning"], width=1.5, dash="dot"),
            ))
        if "vol_6m" in vol_df.columns:
            fig_vol.add_trace(go.Scatter(
                x=vol_df["ym"], y=vol_df["vol_6m"],
                mode="lines+markers", name="6개월",
                line=dict(color=COLORS["primary"], width=2), marker=dict(size=4),
            ))
        st.plotly_chart(fig_vol, use_container_width=True, key="chart_vol")

    # Drawdown 차트
    dd_series = mdd["drawdown_series"]
    if not dd_series.empty:
        fig_dd = create_figure(
            title="Drawdown (전고점 대비 하락폭)",
            xaxis_title="년월", yaxis_title="하락폭 (%)",
            xaxis_tickangle=-45,
        )
        fig_dd.add_trace(go.Scatter(
            x=dd_series["ym"], y=dd_series["drawdown_pct"],
            mode="lines", name="Drawdown",
            fill="tozeroy", fillcolor="rgba(220,38,38,0.1)",
            line=dict(color=COLORS["down"], width=1.5),
        ))
        fig_dd.add_hline(y=0, line_color="#cbd5e1")
        st.plotly_chart(fig_dd, use_container_width=True, key="chart_dd")

    # 월별 거래건수
    liq_counts = liq["monthly_counts"]
    if not liq_counts.empty:
        fig_liq = create_figure(
            title="월별 거래건수 (단지 vs 동 전체)",
            xaxis_title="년월", yaxis_title="거래건수",
            xaxis_tickangle=-45, barmode="group",
        )
        fig_liq.add_trace(go.Bar(
            x=liq_counts["ym"], y=liq_counts["apt_count"],
            name=selected_apt, marker_color=COLORS["primary"], opacity=0.85,
        ))
        fig_liq.add_trace(go.Scatter(
            x=liq_counts["ym"], y=liq_counts["dong_count"],
            mode="lines+markers", name=f"{selected_dong} 전체",
            line=dict(color=COLORS["neutral"], width=1.5, dash="dash"),
            marker=dict(size=4),
        ))
        st.plotly_chart(fig_liq, use_container_width=True, key="chart_liq")


# =====================================================
# Tab 3: 비교 단지 분석
# =====================================================
with tab3:
    st.subheader("비교 단지 분석")
    st.markdown(f"""
    **{selected_apt}**와 비슷한 조건의 단지를 자동으로 찾아 비교합니다.
    같은 {selected_gu} 내에서 건축연도 +-5년, 비슷한 면적대의 단지를 선별합니다.
    - **프리미엄이 양수(+)**: 비교 단지보다 비싸게 거래됨 = 시장에서 더 높이 평가
    - **프리미엄이 음수(-)**: 비교 단지보다 싸게 거래됨 = 저평가 가능성 or 약점 존재
    """)

    comparables = find_comparable_complexes(
        df_gu, selected_apt, build_year, target_area,
    )

    if comparables.empty or len(comparables) < 2:
        st.info("비교 가능한 단지가 부족합니다.")
    else:
        # 프리미엄/디스카운트
        target_row = comparables[comparables["is_target"]]
        others = comparables[~comparables["is_target"]]
        if not target_row.empty and not others.empty:
            target_sqm = target_row["median_sqm"].iloc[0]
            others_avg = others["median_sqm"].mean()
            premium = round((target_sqm - others_avg) / others_avg * 100, 1) if others_avg > 0 else 0

            pc1, pc2, pc3 = st.columns(3)
            pc1.metric(f"{selected_apt} m2당가", f"{target_sqm:,.1f}만원/m2")
            pc2.metric("비교 단지 평균", f"{others_avg:,.1f}만원/m2")
            pc3.metric("프리미엄", f"{premium:+.1f}%")

        st.divider()

        # 바차트
        comp_sorted = comparables.sort_values("median_sqm")
        bar_colors = [
            COLORS["primary"] if t else COLORS["primary_light"]
            for t in comp_sorted["is_target"]
        ]
        fig_comp = create_figure(
            title=f"비교 단지 m2당 가격 ({selected_gu})",
            xaxis_title="m2당 가격 (만원/m2)", yaxis_title="",
            height=max(300, len(comp_sorted) * 35),
        )
        fig_comp.add_trace(go.Bar(
            x=comp_sorted["median_sqm"],
            y=comp_sorted["apt_name"] + " (" + comp_sorted["dong"] + ")",
            orientation="h",
            marker_color=bar_colors,
            text=[f"{v:,.1f}" for v in comp_sorted["median_sqm"]],
            textposition="outside",
        ))
        st.plotly_chart(fig_comp, use_container_width=True, key="chart_comp_bar")

        # 시계열 비교 (상위 3개 + 타겟)
        top_comps = comparables.head(4)["apt_name"].tolist()
        if selected_apt not in top_comps:
            top_comps = [selected_apt] + top_comps[:3]

        fig_ts = create_figure(
            title="비교 단지 가격 추이",
            xaxis_title="년월", yaxis_title="중위가 (만원)",
            hovermode="x unified", xaxis_tickangle=-45,
        )
        for i, apt in enumerate(top_comps):
            apt_data = df_gu[df_gu["apt_name"] == apt]
            if apt_area > 0:
                apt_data = apt_data[apt_data["area"].round(0).astype(int) == apt_area]
            h = apt_data.groupby("ym")["price"].median().reset_index().sort_values("ym")
            if h.empty:
                continue
            color = COLORS["primary"] if apt == selected_apt else CATEGORICAL_10[(i + 1) % len(CATEGORICAL_10)]
            width = 2.5 if apt == selected_apt else 1.5
            fig_ts.add_trace(go.Scatter(
                x=h["ym"], y=h["price"],
                mode="lines+markers", name=apt,
                line=dict(color=color, width=width),
                marker=dict(size=4 if apt != selected_apt else 6),
            ))
        st.plotly_chart(fig_ts, use_container_width=True, key="chart_comp_ts")

        # 비교 테이블
        st.markdown("**비교 단지 상세**")
        comp_display = comparables.rename(columns={
            "apt_name": "단지명", "dong": "동", "build_year": "건축년도",
            "median_price": "중위가(만원)", "median_sqm": "m2당가",
            "trade_count": "거래건수", "change_pct": "상승률(%)", "is_target": "선택",
        })
        comp_display["선택"] = comp_display["선택"].apply(lambda x: "★" if x else "")
        st.dataframe(
            comp_display[["선택", "단지명", "동", "건축년도", "중위가(만원)", "m2당가", "상승률(%)", "거래건수"]],
            use_container_width=True, hide_index=True,
            height=calc_table_height(len(comp_display)),
        )


# =====================================================
# Tab 4: 투자 스코어카드
# =====================================================
with tab4:
    st.subheader("투자 스코어카드")
    st.markdown("""
    6가지 핵심 지표를 0~100점으로 환산하여 종합 투자 매력도를 평가합니다.

    | 항목 | 의미 | 높은 점수일 때 |
    |------|------|--------------|
    | **가격 추세** | 최근 6개월 가격 방향 | 가격이 오르고 있음 |
    | **전세가율** | 전세가 / 매매가 비율 | 전세 수요가 탄탄함 |
    | **유동성** | 같은 동네 대비 거래 빈도 | 사고팔기 쉬움 |
    | **안정성** | 가격 변동 크기 (역산) | 가격이 안정적임 |
    | **갭 안전성** | 매매-전세 차이 크기 (역산) | 갭이 작아 깡통전세 위험 낮음 |
    | **비교 우위** | 비슷한 단지 내 가격 순위 | 동급 단지 중 높이 평가받음 |
    """)

    # 데이터 수집
    # 1. 가격 추세 (6개월 상승률)
    change_6m = 0.0
    if len(history) >= 6:
        p6 = history["median_price"].iloc[-6]
        p_now = history["median_price"].iloc[-1]
        change_6m = round((p_now - p6) / p6 * 100, 1) if p6 > 0 else 0

    # 2. 전세가율
    jeonse_ratio_val = 0.0
    try:
        @st.cache_data(show_spinner=False)
        def _get_rent(gus, s, e):
            codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
            return collect_seoul_rent_data(s, e, codes)

        rent_raw = _get_rent(tuple(selected_gus), start_ym, end_ym)
        if not rent_raw.empty:
            rent_clean = clean_rent_data(rent_raw)
            apt_jeonse = rent_clean[
                (rent_clean["apt_name"] == selected_apt) & (rent_clean["rent_type"] == "전세")
            ]
            if apt_area > 0:
                apt_jeonse = apt_jeonse[apt_jeonse["area"].round(0).astype(int) == apt_area]
            if not apt_jeonse.empty and not df_apt.empty:
                med_deposit = apt_jeonse["deposit"].median()
                med_price = df_apt["price"].median()
                jeonse_ratio_val = round(med_deposit / med_price * 100, 1) if med_price > 0 else 0
    except Exception:
        pass

    # 3. 유동성
    liq = calc_liquidity_score(df_apt, df_dong)

    # 4. 변동성
    vol_score_val = 0.0
    vol_df2 = calc_rolling_volatility(history)
    if not vol_df2.empty and "vol_6m" in vol_df2.columns:
        recent_v = vol_df2["vol_6m"].iloc[-1]
        vol_score_val = recent_v if not pd.isna(recent_v) else 0

    # 5. 갭 비율
    gap_ratio_val = 100 - jeonse_ratio_val if jeonse_ratio_val > 0 else 30

    # 6. 비교 우위
    comp_rank_pct = 50.0
    if not comparables.empty:
        comp_sorted_rank = comparables.sort_values("median_sqm", ascending=False).reset_index(drop=True)
        target_idx = comp_sorted_rank[comp_sorted_rank["is_target"]].index
        if len(target_idx) > 0:
            rank = target_idx[0]
            comp_rank_pct = round((1 - rank / max(len(comp_sorted_rank) - 1, 1)) * 100)

    scores = calc_investment_score(
        change_6m, jeonse_ratio_val, liq["liquidity_ratio"],
        vol_score_val, gap_ratio_val, comp_rank_pct,
    )

    # KPI
    sc1, sc2 = st.columns([1, 2])
    with sc1:
        st.metric("종합 점수", f"{scores['total']}/100")
        if scores["strengths"]:
            st.success(f"강점: {', '.join(scores['strengths'])}")
        if scores["weaknesses"]:
            st.error(f"약점: {', '.join(scores['weaknesses'])}")

    with sc2:
        # 레이더 차트
        categories = list(scores["scores"].keys())
        values = list(scores["scores"].values())
        values_closed = values + [values[0]]
        categories_closed = categories + [categories[0]]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=values_closed, theta=categories_closed,
            fill="toself", fillcolor="rgba(37,99,235,0.15)",
            line=dict(color=COLORS["primary"], width=2),
            name=selected_apt,
        ))
        # 50점 참조선
        fig_radar.add_trace(go.Scatterpolar(
            r=[50] * (len(categories) + 1), theta=categories_closed,
            line=dict(color="#cbd5e1", width=1, dash="dash"),
            name="기준 (50점)",
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10))),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15),
            height=350,
            margin=dict(l=60, r=60, t=30, b=30),
        )
        st.plotly_chart(fig_radar, use_container_width=True, key="chart_radar")

    # 점수 상세 테이블
    st.divider()
    _interpret = {
        "가격 추세": {True: "상승 흐름이 뚜렷합니다", False: "하락 또는 정체 구간입니다"},
        "전세가율": {True: "전세 수요가 매매가를 뒷받침합니다", False: "전세 수요 대비 매매가가 높습니다"},
        "유동성": {True: "거래가 활발해 매도 시 유리합니다", False: "거래가 적어 매도에 시간이 걸릴 수 있습니다"},
        "안정성": {True: "가격 변동이 작아 예측 가능합니다", False: "가격 변동이 커서 리스크 관리 필요"},
        "갭 안전성": {True: "매매-전세 차이가 작아 안전합니다", False: "갭이 커서 하락 시 깡통전세 위험"},
        "비교 우위": {True: "동급 단지 중 높은 평가를 받고 있습니다", False: "동급 단지 대비 가격 경쟁력이 낮습니다"},
    }
    score_df = pd.DataFrame([
        {"항목": k, "점수": v,
         "등급": "우수" if v >= 70 else ("양호" if v >= 50 else ("주의" if v >= 30 else "위험")),
         "해석": _interpret.get(k, {}).get(v >= 50, "")}
        for k, v in scores["scores"].items()
    ])
    st.dataframe(score_df, use_container_width=True, hide_index=True,
                 height=calc_table_height(len(score_df)))

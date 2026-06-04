import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime

from config import GU_NAME_TO_CODE, AREA_CATEGORIES
from data_collector import collect_seoul_data, collect_seoul_rent_data
from data_processor import (
    clean_trade_data,
    clean_rent_data,
    add_area_category,
    filter_by_area,
    filter_by_build_year,
    filter_outliers,
    get_apt_price_history,
    aggregate_by_gu_month,
    aggregate_rent_by_gu_month,
    calc_jeonse_ratio,
)
from factor_model import (
    build_factor_returns,
    inject_jeonse_factor,
    calc_alpha_beta,
    decompose_returns,
    FACTOR_LABELS,
)
from design_system import (show_chart,
    COLORS, CATEGORICAL_10, apply_theme, create_figure,
    format_price, format_pct, calc_table_height,
)
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()
st.header("알파 / 베타 분석")

st.markdown("""
아파트 가격 변동을 **시장 요인(베타)**과 **단지 고유 성과(알파)**로 분리합니다.

- **베타**: 서울 전체 시장, 구 효과, 면적대 효과, 연식 효과, 전세시장 압력 등 "시장이 움직여서 같이 움직인 부분"
- **알파**: 위 요인을 모두 제거한 후 남는 "이 단지만의 고유 가치 변동"

알파가 양수면 시장보다 잘한 것, 음수면 시장보다 못한 것입니다.
""")

selected_gus = st.session_state.get("selected_gus", [])
start_ym = st.session_state.get("start_ym", "202401")
end_ym = st.session_state.get("end_ym", "202412")

if not selected_gus:
    st.info("사이드바에서 구를 선택하세요.")
    st.stop()

# --- 데이터 로드 (서울 전체 필요 — 베타 팩터 구축용) ---
@st.cache_data(show_spinner="서울 전체 데이터 수집 중 (팩터 구축용)...")
def get_all_data(s_ym, e_ym):
    return collect_seoul_data(s_ym, e_ym)

@st.cache_data(show_spinner="선택 구 데이터 수집 중...")
def get_gu_data(gus, s_ym, e_ym):
    codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
    return collect_seoul_data(s_ym, e_ym, codes)

raw_all = get_all_data(start_ym, end_ym)
raw_gu = get_gu_data(tuple(selected_gus), start_ym, end_ym)

if raw_all.empty or raw_gu.empty:
    st.warning("데이터가 없습니다.")
    st.stop()

df_all = clean_trade_data(raw_all)
df_all = add_area_category(df_all)
df_all = filter_outliers(df_all, st.session_state.get("exclude_outliers", True))

df_gu_full = clean_trade_data(raw_gu)
df_gu_full = add_area_category(df_gu_full)
df_gu_full = filter_outliers(df_gu_full, st.session_state.get("exclude_outliers", True))

if df_gu_full.empty:
    st.warning("데이터가 없습니다.")
    st.stop()

# --- 단지 선택 ---
as1 = st.columns(2)
with as1[0]:
    gu_opts = sorted(df_gu_full["gu_name"].dropna().unique())
    selected_gu = st.selectbox("구", gu_opts, key="alpha_gu")
df_gu = df_gu_full[df_gu_full["gu_name"] == selected_gu]

with as1[1]:
    dong_opts = ["전체"] + sorted(df_gu["dong"].dropna().unique())
    selected_dong = st.selectbox("동", dong_opts, key="alpha_dong")
df_dong = df_gu if selected_dong == "전체" else df_gu[df_gu["dong"] == selected_dong]

as2 = st.columns(2)
with as2[0]:
    apt_counts = df_dong["apt_name"].value_counts()
    selected_apt = st.selectbox("단지", apt_counts.index.tolist(), key="alpha_apt")
df_apt_all = df_dong[df_dong["apt_name"] == selected_apt]

with as2[1]:
    if not df_apt_all.empty:
        areas = df_apt_all["area"].dropna().round(0).astype(int)
        area_counts = areas.value_counts().sort_index()
        area_labels = {0: "전체"}
        for a in area_counts.index:
            area_labels[a] = f"{a}m2 ({area_counts[a]}건)"
        area_keys = [0] + list(area_counts.index)
        apt_area = st.selectbox("전용면적", area_keys,
                                format_func=lambda x: area_labels.get(x, str(x)),
                                key="alpha_area")
    else:
        apt_area = 0

if apt_area == 0:
    df_apt = df_apt_all
else:
    df_apt = df_apt_all[df_apt_all["area"].round(0).astype(int) == apt_area]

if df_apt.empty:
    st.warning("거래 데이터가 없습니다.")
    st.stop()

# --- 팩터 모델 계산 ---
history = get_apt_price_history(df_apt, selected_apt)

if len(history) < 8:
    st.warning(f"알파/베타 분석에 최소 8개월 데이터가 필요합니다. (현재 {len(history)}개월)")
    st.stop()

# 면적대/연식 카테고리 결정
area_cat = df_apt["area_category"].mode().iloc[0] if "area_category" in df_apt.columns and not df_apt["area_category"].mode().empty else None
build_yr = df_apt["build_year"].median() if df_apt["build_year"].notna().any() else None
cur_year = datetime.today().year
age_cat = None
if build_yr:
    if build_yr >= cur_year - 5:
        age_cat = "신축"
    elif build_yr >= cur_year - 10:
        age_cat = "준신축"
    elif build_yr >= cur_year - 20:
        age_cat = "중축"
    else:
        age_cat = "구축"

# 팩터 수익률 구축
factor_returns = build_factor_returns(df_all, selected_gu, area_cat, age_cat)

# 전세가율 팩터 주입 (가능한 경우)
try:
    @st.cache_data(show_spinner=False)
    def _get_rent(gus, s, e):
        codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
        return collect_seoul_rent_data(s, e, codes)

    rent_raw = _get_rent(tuple(selected_gus), start_ym, end_ym)
    if not rent_raw.empty:
        rent_clean = clean_rent_data(rent_raw)
        gu_agg = aggregate_by_gu_month(df_gu)
        rent_agg = aggregate_rent_by_gu_month(rent_clean)
        jeonse_df = calc_jeonse_ratio(gu_agg, rent_agg)
        if not jeonse_df.empty:
            factor_returns = inject_jeonse_factor(factor_returns, jeonse_df, selected_gu)
except Exception:
    pass

# 알파/베타 회귀
result = calc_alpha_beta(history, factor_returns)

if result is None:
    st.warning("알파/베타 계산에 충분한 데이터가 없습니다.")
    st.stop()

st.divider()

# --- 3개 탭 ---
tab1, tab2, tab3 = st.tabs(["수익률 분해", "알파 추이", "베타 프로필"])

# =====================================================
# Tab 1: 수익률 분해
# =====================================================
with tab1:
    st.subheader("수익률 분해")
    st.markdown(f"""
    **{selected_apt}**의 가격 변동을 시장 요인별로 분해합니다.
    각 막대의 색상은 어떤 요인이 가격을 올렸는지(+) 내렸는지(-)를 보여줍니다.
    맨 위의 빨간/파란 부분이 **알파** — 시장으로 설명되지 않는 이 단지만의 성과입니다.
    """)

    # 기여도 KPI
    contrib = result["factor_contribution"]
    total_return = sum(contrib.values())

    kpi_cols = st.columns(min(len(contrib), 4))
    for i, (name, val) in enumerate(contrib.items()):
        col_idx = i % len(kpi_cols)
        kpi_cols[col_idx].metric(name, f"{val:+.1f}%p")

    st.caption(f"기간 총 수익률: {total_return:+.1f}%p / 모델 설명력 R²: {result['r_squared']:.1%}")

    if result["r_squared"] < 0.15:
        st.warning("R²가 낮아 팩터 모델의 설명력이 제한적입니다. 거래 데이터가 적거나, 이 단지의 가격이 시장 팩터와 다른 요인에 의해 움직이고 있을 수 있습니다.")

    st.divider()

    # 스택 바차트
    decomp_df = decompose_returns(
        history, factor_returns,
        result["latest_betas"], result["available_factors"],
        alpha_monthly=result["latest_alpha"],
    )

    if not decomp_df.empty:
        # 팩터 색상 매핑
        factor_colors = {
            "서울 시장": COLORS["primary"],
            "구 효과": COLORS["up"],
            "면적대 효과": COLORS["warning"],
            "연식 효과": COLORS["accent"],
            "전세시장 압력": "#0891b2",
            "알파 (고유)": COLORS["up"],
            "잔차": "#cbd5e1",
        }

        fig = create_figure(
            title="월별 수익률 팩터 분해 (%)",
            xaxis_title="년월", yaxis_title="수익률 기여 (%p)",
            barmode="relative", xaxis_tickangle=-45,
        )

        # 팩터별 바 추가
        value_cols = [c for c in decomp_df.columns if c not in ["ym", "actual_return"]]
        for col in value_cols:
            color = factor_colors.get(col, COLORS["neutral"])
            fig.add_trace(go.Bar(
                x=decomp_df["ym"], y=decomp_df[col],
                name=col, marker_color=color,
                hovertemplate=f"{col}: " + "%{y:+.1f}%p<extra></extra>",
            ))

        # 실제 수익률 라인
        fig.add_trace(go.Scatter(
            x=decomp_df["ym"], y=decomp_df["actual_return"],
            mode="lines+markers", name="실제 수익률",
            line=dict(color=COLORS["text_primary"], width=2, dash="dot"),
            marker=dict(size=5),
        ))

        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=-0.3),
            height=380,
        )
        show_chart(fig, use_container_width=True, key="chart_decomp_bar")

        st.markdown("""
        **읽는 법**: 각 월의 막대를 합치면 실제 수익률(점선)과 일치합니다.
        파란색(서울 시장)이 크면 "시장을 탔다", 빨간색(알파)이 크면 "이 단지가 특별하다"는 의미입니다.
        """)


# =====================================================
# Tab 2: 알파 추이
# =====================================================
with tab2:
    st.subheader("알파 추이")
    st.markdown("""
    **롤링 12개월 알파**: 최근 12개월간 시장 요인을 제거한 후 남는 단지 고유 성과입니다.
    - **0 위**: 시장보다 잘하고 있음 (고유 가치가 인정받는 중)
    - **0 아래**: 시장보다 못하고 있음 (과대평가 해소 or 약점 노출)
    - **추세 변화**: 양→음 반전은 주의 시그널, 음→양 반전은 기회 시그널
    """)

    alpha_df = result["alpha_series"]

    if alpha_df.empty or len(alpha_df) < 2:
        st.info("알파 추이를 보려면 더 긴 기간의 데이터가 필요합니다.")
    else:
        latest_alpha = alpha_df["alpha"].iloc[-1]

        a1, a2 = st.columns(2)
        a1.metric("최근 알파", f"{latest_alpha:+.3f}%p/월",
                  delta="시장 대비 초과 성과" if latest_alpha > 0 else "시장 대비 부진",
                  delta_color="normal" if latest_alpha > 0 else "inverse")

        # 알파 평균 대비 현재 위치
        avg_alpha = alpha_df["alpha"].mean()
        a2.metric("기간 평균 알파", f"{avg_alpha:+.3f}%p/월",
                  delta=f"현재 {'평균 위' if latest_alpha > avg_alpha else '평균 아래'}",
                  delta_color="off")

        st.divider()

        # 알파 라인차트
        fig_alpha = create_figure(
            title=f"{selected_apt} 롤링 알파 (12개월)",
            xaxis_title="년월", yaxis_title="알파 (%p/월)",
            xaxis_tickangle=-45,
        )

        # 양/음 영역 색상 구분
        fig_alpha.add_trace(go.Scatter(
            x=alpha_df["ym"], y=alpha_df["alpha"],
            mode="lines+markers",
            line=dict(color=COLORS["primary"], width=2.5),
            marker=dict(
                size=6,
                color=[COLORS["up"] if a > 0 else COLORS["down"] for a in alpha_df["alpha"]],
            ),
            fill="tozeroy",
            fillcolor="rgba(37,99,235,0.06)",
            hovertemplate="%{x}<br>알파: %{y:+.3f}%p<extra></extra>",
            name="알파",
        ))
        fig_alpha.add_hline(y=0, line_color="#cbd5e1", line_width=1)

        # 평균선
        fig_alpha.add_hline(
            y=avg_alpha, line_dash="dash", line_color=COLORS["accent"],
            annotation_text=f"평균 {avg_alpha:+.3f}",
            annotation_font_color=COLORS["accent"],
        )

        show_chart(fig_alpha, use_container_width=True, key="chart_alpha_line")

        # 알파 해석
        if len(alpha_df) >= 3:
            recent_3 = alpha_df["alpha"].tail(3).mean()
            older = alpha_df["alpha"].iloc[:-3].mean() if len(alpha_df) > 3 else 0
            if recent_3 > 0 and older <= 0:
                st.success("알파가 음에서 양으로 반전 중 — 저평가 해소 가능성")
            elif recent_3 < 0 and older >= 0:
                st.warning("알파가 양에서 음으로 반전 중 — 과대평가 조정 주의")
            elif recent_3 > avg_alpha:
                st.info("최근 알파가 평균 위에서 유지 중 — 고유 가치 강세")
            else:
                st.info("최근 알파가 평균 아래 — 시장 대비 부진 구간")


# =====================================================
# Tab 3: 베타 프로필
# =====================================================
with tab3:
    st.subheader("베타 프로필")
    st.markdown(f"""
    **{selected_apt}**이 각 시장 요인에 얼마나 민감한지를 보여줍니다.
    - **베타 > 1**: 해당 요인이 오를 때 이 단지는 더 많이 오름 (공격적)
    - **베타 ≈ 1**: 시장과 비슷하게 움직임 (중립)
    - **베타 < 1**: 해당 요인 변화에 둔감 (방어적)
    - **베타 < 0**: 해당 요인과 반대로 움직임 (역상관)

    R²가 높을수록 이 단지의 가격이 시장 요인으로 잘 설명됩니다.
    R²가 낮을수록(= 1 - R²가 높을수록) 알파가 중요한 단지입니다.
    """)

    betas = result["latest_betas"]
    r_sq = result["r_squared"]

    b1, b2 = st.columns(2)
    b1.metric("모델 설명력 (R²)", f"{r_sq:.1%}",
              delta=f"알파 기여 {1 - r_sq:.1%}", delta_color="off")
    b2.metric("팩터 수", f"{len(betas)}개")

    st.divider()

    if betas:
        categories = [FACTOR_LABELS.get(f, f) for f in betas.keys()]
        values = list(betas.values())

        # 수평 바차트 — 양/음 베타를 직관적으로 표현
        beta_bar_df = pd.DataFrame({"팩터": categories, "베타": values})
        beta_bar_df = beta_bar_df.sort_values("베타")

        bar_colors = [
            COLORS["primary"] if v >= 0 else COLORS["down"]
            for v in beta_bar_df["베타"]
        ]

        fig_beta = create_figure(
            title=f"{selected_apt} 베타 계수",
            xaxis_title="베타 (β)", yaxis_title="",
            height=max(250, len(beta_bar_df) * 50),
        )
        fig_beta.add_trace(go.Bar(
            x=beta_bar_df["베타"], y=beta_bar_df["팩터"],
            orientation="h", marker_color=bar_colors,
            text=[f"{v:+.2f}" for v in beta_bar_df["베타"]],
            textposition="outside",
            hovertemplate="%{y}: β=%{x:+.3f}<extra></extra>",
        ))
        # β=1 기준선
        fig_beta.add_vline(x=1, line_dash="dash", line_color=COLORS["neutral"],
                           annotation_text="β=1 (시장과 동일)", annotation_font_size=10)
        fig_beta.add_vline(x=0, line_color="#e2e8f0")

        show_chart(fig_beta, use_container_width=True, key="chart_beta_bar")

        st.caption("""
        **β > 1**: 시장보다 더 크게 반응 (공격적) /
        **0 < β < 1**: 시장보다 덜 반응 (방어적) /
        **β < 0**: 시장과 반대로 움직임 (헤지)
        """)

        # 베타 해석 테이블
        beta_rows = []
        for f, v in betas.items():
            label = FACTOR_LABELS.get(f, f)
            if abs(v) < 0.2:
                sensitivity = "무관"
                desc = "이 요인과 거의 무관하게 움직임"
            elif v > 1.5:
                sensitivity = "매우 민감"
                desc = "이 요인이 오르면 훨씬 더 오름"
            elif v > 0.8:
                sensitivity = "민감"
                desc = "이 요인과 비슷하게 움직임"
            elif v > 0.2:
                sensitivity = "약한 민감"
                desc = "이 요인에 약하게 반응"
            elif v < -0.5:
                sensitivity = "역상관"
                desc = "이 요인과 반대로 움직임 (헤지 효과)"
            else:
                sensitivity = "약한 역상관"
                desc = "이 요인과 약하게 반대로 움직임"

            beta_rows.append({
                "팩터": label,
                "베타": f"{v:+.2f}",
                "민감도": sensitivity,
                "해석": desc,
            })

        st.dataframe(
            pd.DataFrame(beta_rows),
            use_container_width=True, hide_index=True,
            height=calc_table_height(len(beta_rows)),
        )

    # 롤링 베타 시계열 (있는 경우)
    beta_series = result["beta_series"]
    if not beta_series.empty and len(beta_series) > 2:
        st.divider()
        st.markdown("**베타 추이 (시간에 따른 민감도 변화)**")

        fig_beta_ts = create_figure(
            title="롤링 베타 추이",
            xaxis_title="년월", yaxis_title="베타 계수",
            hovermode="x unified", xaxis_tickangle=-45,
        )

        beta_cols = [c for c in beta_series.columns if c.startswith("beta_")]
        for i, col in enumerate(beta_cols):
            factor_key = col.replace("beta_", "")
            label = FACTOR_LABELS.get(factor_key, factor_key)
            color = CATEGORICAL_10[i % len(CATEGORICAL_10)]
            fig_beta_ts.add_trace(go.Scatter(
                x=beta_series["ym"], y=beta_series[col],
                mode="lines", name=label,
                line=dict(color=color, width=2),
            ))

        fig_beta_ts.add_hline(y=1, line_dash="dash", line_color="#cbd5e1",
                              annotation_text="β=1 (시장과 동일)")
        fig_beta_ts.add_hline(y=0, line_color="#e2e8f0")

        show_chart(fig_beta_ts, use_container_width=True, key="chart_beta_ts")

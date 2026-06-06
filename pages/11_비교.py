"""아파트 비교 — 답 먼저 세로 스택 (탭 제거).

여러 단지를 같은 면적대에서 비교한다. 비교의 핵심 질문은 "누가 더 올랐나"이므로
수익률 인덱스를 최상단으로 끌어올리고, m²당/총가 추이는 토글 하나로 통합한다.
상세 수치 표는 전문가용으로 접는다.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from data_pipeline import current_filters, load_trade
from design_system import (
    show_chart, COLORS, CATEGORICAL_10, create_figure,
    format_price, format_sqm_price, calc_table_height,
    verdict_card, hero_metrics, pro_section,
)
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()
st.header("아파트 비교")
st.caption("같은 면적대끼리 비교해야 의미가 있습니다. 타겟 면적을 먼저 정하고 단지를 검색해 고르세요.")

f = current_filters()
selected_gus = f["gus"]
if not selected_gus:
    st.info("사이드바에서 구를 선택하세요.")
    st.stop()

df = load_trade(
    selected_gus, f["start_ym"], f["end_ym"],
    area=None, build_year=None,
    exclude_outliers=f["exclude_outliers"],
)
if df.empty:
    st.warning("데이터가 없습니다.")
    st.stop()

# --- 비교 조건 ---
c1, c2 = st.columns(2)
target_area = c1.selectbox("타겟 면적 (m2)", [59, 84, 85, 102, 114, 135], index=2,
                           format_func=lambda x: f"{x}m2")
area_tol = c2.selectbox("허용 오차", [3, 5, 10], index=1,
                        format_func=lambda x: f"+-{x}m2")

df_area = df[(df["area"] >= target_area - area_tol) & (df["area"] <= target_area + area_tol)]
if df_area.empty:
    st.warning(f"{target_area}m2 +-{area_tol} 범위의 거래가 없습니다.")
    st.stop()

# --- 단지 선택 (검색형 multiselect) ---
apt_stats = (
    df_area.groupby(["gu_name", "dong", "apt_name"])
    .agg(trades=("price", "count"))
    .reset_index()
    .sort_values("trades", ascending=False)
)
apt_stats["label"] = (
    apt_stats["apt_name"] + " [" + apt_stats["gu_name"] + " " +
    apt_stats["dong"] + ", " + apt_stats["trades"].astype(str) + "건]"
)
apt_lookup = {row["label"]: (row["apt_name"], row["gu_name"], row["dong"])
              for _, row in apt_stats.iterrows()}

selected_labels = st.multiselect(
    "비교할 단지 (타이핑으로 검색, 최대 8개)",
    apt_stats["label"].tolist(), max_selections=8,
)
if not selected_labels:
    st.info("비교할 단지를 선택하세요. 단지명으로 검색할 수 있습니다.")
    st.stop()

# --- 단지별 월별 시계열 + 요약 통계 (한 번만 계산해 전 구간에서 재사용) ---
compare_data = {}
display_names = []
for label in selected_labels:
    apt_name, gu, dong = apt_lookup.get(label, (label.split(" [")[0], "", ""))
    apt_df = df_area[df_area["apt_name"] == apt_name]
    if gu:
        apt_df = apt_df[apt_df["gu_name"] == gu]
    if dong:
        apt_df = apt_df[apt_df["dong"] == dong]
    if apt_df.empty:
        continue

    name = f"{apt_name} ({dong})" if dong else apt_name
    monthly = (
        apt_df.groupby("ym")
        .agg(median_price=("price", "median"),
             median_sqm=("price_per_sqm", "median"))
        .reset_index().sort_values("ym")
    )
    base = monthly["median_sqm"].iloc[0] if not monthly.empty else 0
    last = monthly["median_sqm"].iloc[-1] if not monthly.empty else 0
    ret = round((last - base) / base * 100, 1) if base > 0 else 0.0
    if len(monthly) >= 6:
        m6 = monthly["median_sqm"].iloc[-6]
        momentum = round((last - m6) / m6 * 100, 1) if m6 > 0 else ret
    else:
        momentum = ret

    display_names.append(name)
    compare_data[name] = {
        "monthly": monthly, "gu": gu, "dong": dong,
        "build_year": int(apt_df["build_year"].median()) if apt_df["build_year"].notna().any() else 0,
        "total_trades": len(apt_df),
        "latest_price": monthly["median_price"].iloc[-1] if not monthly.empty else 0,
        "latest_sqm": last,
        "ret": ret, "momentum": momentum,
    }

if not display_names:
    st.warning("선택한 단지의 거래 데이터가 없습니다.")
    st.stop()

# 색상: 단지 순서 고정 → 모든 차트에서 동일 색 (레전드 중복 방지)
color_of = {name: CATEGORICAL_10[i % len(CATEGORICAL_10)] for i, name in enumerate(display_names)}
all_yms = sorted(set().union(*[
    set(compare_data[n]["monthly"]["ym"]) for n in display_names
    if not compare_data[n]["monthly"].empty
]))

st.divider()

# --- 1. 판정 카드 (한 문장 답) ---
ranked = sorted(display_names, key=lambda n: compare_data[n]["ret"], reverse=True)
best_ret = ranked[0]
best_mom = max(display_names, key=lambda n: compare_data[n]["momentum"])
headline = f"{len(display_names)}개 단지 중 '{best_ret}'가 기간 수익률 {compare_data[best_ret]['ret']:+.1f}%로 1위"
sub = f"최근 6개월 상승세는 '{best_mom}'({compare_data[best_mom]['momentum']:+.1f}%)가 가장 강합니다."
verdict_card(headline, sub=sub)

# --- 2. 비교 단지 요약 (4개씩 줄바꿈) ---
kpi_cols = st.columns(min(len(display_names), 4))
for i, name in enumerate(display_names):
    d = compare_data[name]
    kpi_cols[i % len(kpi_cols)].metric(
        name, format_price(d["latest_price"]),
        delta=f"{d['gu']} {d['dong']} / {d['build_year']}년", delta_color="off",
    )

st.divider()

# --- 3. 수익률 비교 (핵심): 인덱스 + 기간 수익률 바 ---
st.markdown("#### 누가 더 올랐나")
st.caption("시작 시점을 100으로 맞춰 면적당 가격의 상대 변화를 비교합니다.")

fig_idx = create_figure(
    xaxis_title="년월", yaxis_title="인덱스 (시작=100)",
    xaxis_categoryorder="array", xaxis_categoryarray=all_yms,
    hovermode="x unified", xaxis_tickangle=-45, height=380,
)
fig_idx.add_hline(y=100, line_color="#cbd5e1", line_dash="dot")
for name in display_names:
    m = compare_data[name]["monthly"]
    if m.empty or len(m) < 2:
        continue
    base = m["median_sqm"].iloc[0]
    if base <= 0:
        continue
    indexed = (m["median_sqm"] / base * 100).round(1)
    fig_idx.add_trace(go.Scatter(
        x=m["ym"], y=indexed, mode="lines+markers", name=name,
        line=dict(color=color_of[name], width=2.5), marker=dict(size=5),
        hovertemplate="<b>" + name + "</b><br>%{y:.1f}<extra></extra>",
    ))
show_chart(fig_idx, key="chart_compare_index")

# 기간 수익률 가로 바 (단지명이 곧 레전드 역할)
ret_rows = [{"단지": n, "수익률": compare_data[n]["ret"]} for n in display_names]
ret_df = pd.DataFrame(ret_rows).sort_values("수익률")
fig_ret = create_figure(
    xaxis_title="기간 수익률 (%)", yaxis_title="",
    height=max(180, len(ret_df) * 44), xaxis_type="linear",
)
fig_ret.add_trace(go.Bar(
    x=ret_df["수익률"], y=ret_df["단지"], orientation="h",
    marker_color=[color_of[n] for n in ret_df["단지"]],
    text=[f"{v:+.1f}%" for v in ret_df["수익률"]], textposition="outside",
    hovertemplate="<b>%{y}</b><br>%{x:+.1f}%<extra></extra>",
))
show_chart(fig_ret, key="chart_compare_return")

st.divider()

# --- 4. 가격 추이 (m²당 / 총가 토글 — 차트 하나로 통합) ---
st.markdown("#### 가격 추이")
price_mode = st.radio(
    "가격 기준", ["총가", "m2당가"], horizontal=True,
    key="cmp_price_mode", label_visibility="collapsed",
)
if price_mode == "총가":
    y_col, y_title, fmt = "median_price", "중위가 (만원)", format_price
else:
    y_col, y_title, fmt = "median_sqm", "m2당가 (만원/m2)", format_sqm_price

fig_price = create_figure(
    xaxis_title="년월", yaxis_title=y_title,
    xaxis_categoryorder="array", xaxis_categoryarray=all_yms,
    hovermode="x unified", xaxis_tickangle=-45, height=360,
)
fig_price.update_layout(showlegend=False)  # 색-단지 매핑은 위 차트/바와 동일
for name in display_names:
    m = compare_data[name]["monthly"]
    if m.empty:
        continue
    formatted = [fmt(v) for v in m[y_col]]
    fig_price.add_trace(go.Scatter(
        x=m["ym"], y=m[y_col], mode="lines+markers", name=name,
        line=dict(color=color_of[name], width=2.5), marker=dict(size=5),
        customdata=list(zip([name] * len(m), formatted)),
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
    ))
show_chart(fig_price, key="chart_compare_price")

# --- 5. 상세 수치 (전문가용으로 접기) ---
with pro_section("상세 수치 · 모멘텀"):
    rows = []
    for name in display_names:
        d = compare_data[name]
        rows.append({
            "단지": name, "구": d["gu"], "동": d["dong"], "건축": d["build_year"],
            "m2당가": round(d["latest_sqm"], 1), "중위가(만원)": int(d["latest_price"]),
            "거래수": d["total_trades"], "기간수익률(%)": d["ret"], "6M모멘텀(%)": d["momentum"],
        })
    table_df = pd.DataFrame(rows)
    st.dataframe(
        table_df,
        column_config={
            "m2당가": st.column_config.NumberColumn(format="%.1f"),
            "중위가(만원)": st.column_config.NumberColumn(format="%,d"),
            "기간수익률(%)": st.column_config.NumberColumn(format="%+.1f"),
            "6M모멘텀(%)": st.column_config.NumberColumn(format="%+.1f"),
        },
        use_container_width=True, hide_index=True,
        height=calc_table_height(len(table_df)),
    )

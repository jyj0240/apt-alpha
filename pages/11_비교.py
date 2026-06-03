import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from config import GU_NAME_TO_CODE
from data_collector import collect_seoul_data
from data_processor import (
    clean_trade_data, add_area_category, filter_outliers,
)
from design_system import (
    COLORS, CATEGORICAL_10, apply_theme, create_figure,
    format_price, format_sqm_price, format_pct, calc_table_height,
)
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()
st.header("아파트 비교")

st.markdown("""
관심 단지를 여러 개 선택하여 **같은 차트에서 가격 추이를 비교**합니다.
같은 면적대끼리 비교해야 의미 있으므로, 타겟 면적을 먼저 설정하세요.
""")

selected_gus = st.session_state.get("selected_gus", [])
start_ym = st.session_state.get("start_ym", "202401")
end_ym = st.session_state.get("end_ym", "202412")

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
df = filter_outliers(df, st.session_state.get("exclude_outliers", True))

if df.empty:
    st.warning("데이터가 없습니다.")
    st.stop()

# --- 면적 설정 ---
st.subheader("비교 조건")
c1, c2 = st.columns(2)
target_area = c1.selectbox("타겟 면적 (m2)", [59, 84, 85, 102, 114, 135], index=2,
                           format_func=lambda x: f"{x}m2")
area_tol = c2.selectbox("허용 오차", [3, 5, 10], index=1,
                        format_func=lambda x: f"+-{x}m2")

area_lo = target_area - area_tol
area_hi = target_area + area_tol
df_area = df[(df["area"] >= area_lo) & (df["area"] <= area_hi)]

if df_area.empty:
    st.warning(f"{target_area}m2 +-{area_tol} 범위의 거래가 없습니다.")
    st.stop()

# --- 단지 선택 ---
apt_stats = (
    df_area.groupby(["gu_name", "dong", "apt_name"])
    .agg(trades=("price", "count"), median_sqm=("price_per_sqm", "median"))
    .reset_index()
    .sort_values("trades", ascending=False)
)

apt_stats["label"] = (
    apt_stats["apt_name"] + " [" + apt_stats["gu_name"] + " " +
    apt_stats["dong"] + ", " + apt_stats["trades"].astype(str) + "건]"
)

# 검색 + multiselect
apt_lookup = dict(zip(apt_stats["label"], apt_stats["apt_name"]))
all_labels = apt_stats["label"].tolist()

search_query = st.text_input(
    "단지 검색", placeholder="단지명 입력 (예: 반포, 래미안, 그랑...)",
    help="검색어를 입력하면 아래 목록이 필터링됩니다. 이미 선택한 단지는 유지됩니다.",
)

# 이미 선택된 항목은 검색과 무관하게 항상 옵션에 포함
already_selected = st.session_state.get("compare_apts", [])

if search_query.strip():
    matched = apt_stats[
        apt_stats["apt_name"].str.contains(search_query.strip(), case=False, na=False) |
        apt_stats["dong"].str.contains(search_query.strip(), case=False, na=False)
    ]["label"].tolist()
    st.caption(f"'{search_query}' 검색 결과: {len(matched)}개 단지")
else:
    matched = all_labels

# 이미 선택된 것 + 검색 결과 합치기 (순서: 선택된 것 먼저)
combined = list(dict.fromkeys(already_selected + matched))

selected_labels = st.multiselect(
    "비교할 단지 선택 (최대 8개)",
    combined,
    default=[s for s in already_selected if s in combined],
    max_selections=8,
    key="compare_apts",
)

if not selected_labels:
    st.info("비교할 단지를 선택하세요. 단지명으로 검색할 수 있습니다.")
    st.stop()

selected_apts = [apt_lookup.get(l, l.split("  [")[0].split(" [")[0]) for l in selected_labels]

st.divider()

# --- 선택된 단지 데이터 ---
compare_data = {}
for apt_name in selected_apts:
    apt_df = df_area[df_area["apt_name"] == apt_name]
    monthly = (
        apt_df.groupby("ym")
        .agg(
            median_price=("price", "median"),
            median_sqm=("price_per_sqm", "median"),
            trade_count=("price", "count"),
        )
        .reset_index()
        .sort_values("ym")
    )
    gu = apt_df["gu_name"].iloc[0] if not apt_df.empty else ""
    dong = apt_df["dong"].iloc[0] if not apt_df.empty else ""
    build_yr = int(apt_df["build_year"].median()) if apt_df["build_year"].notna().any() else 0
    compare_data[apt_name] = {
        "monthly": monthly,
        "gu": gu,
        "dong": dong,
        "build_year": build_yr,
        "total_trades": len(apt_df),
        "latest_sqm": monthly["median_sqm"].iloc[-1] if not monthly.empty else 0,
        "latest_price": monthly["median_price"].iloc[-1] if not monthly.empty else 0,
    }

# --- KPI 요약 ---
st.subheader("비교 단지 요약")
kpi_cols = st.columns(min(len(selected_apts), 4))
for i, apt in enumerate(selected_apts):
    d = compare_data[apt]
    col_idx = i % len(kpi_cols)
    kpi_cols[col_idx].metric(
        f"{apt}",
        format_price(d["latest_price"]),
        delta=f"{d['gu']} {d['dong']} / {d['build_year']}년",
        delta_color="off",
    )

st.divider()

# --- 차트 ---
tab1, tab2, tab3, tab4 = st.tabs(["m2당 가격 추이", "총가 추이", "수익률 비교", "상세 테이블"])

# === Tab 1: m2당 가격 추이 ===
with tab1:
    fig_sqm = create_figure(
        title=f"m2당 가격 추이 비교 ({target_area}m2)",
        xaxis_title="년월", yaxis_title="m2당 가격 (만원/m2)",
        hovermode="x unified", xaxis_tickangle=-45,
    )

    for i, apt in enumerate(selected_apts):
        m = compare_data[apt]["monthly"]
        if m.empty:
            continue
        color = CATEGORICAL_10[i % len(CATEGORICAL_10)]
        formatted = [format_sqm_price(v) for v in m["median_sqm"]]
        fig_sqm.add_trace(go.Scatter(
            x=m["ym"], y=m["median_sqm"],
            mode="lines+markers", name=apt,
            line=dict(color=color, width=2.5),
            marker=dict(size=5),
            customdata=list(zip([apt] * len(m), formatted)),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
        ))

    st.plotly_chart(fig_sqm, use_container_width=True, key="chart_compare_sqm")

# === Tab 2: 총가 추이 ===
with tab2:
    fig_price = create_figure(
        title=f"중위 거래가 추이 비교 ({target_area}m2)",
        xaxis_title="년월", yaxis_title="중위가 (만원)",
        hovermode="x unified", xaxis_tickangle=-45,
    )

    for i, apt in enumerate(selected_apts):
        m = compare_data[apt]["monthly"]
        if m.empty:
            continue
        color = CATEGORICAL_10[i % len(CATEGORICAL_10)]
        formatted = [format_price(v) for v in m["median_price"]]
        fig_price.add_trace(go.Scatter(
            x=m["ym"], y=m["median_price"],
            mode="lines+markers", name=apt,
            line=dict(color=color, width=2.5),
            marker=dict(size=5),
            customdata=list(zip([apt] * len(m), formatted)),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
        ))

    st.plotly_chart(fig_price, use_container_width=True, key="chart_compare_price")

# === Tab 3: 수익률 비교 (기준점 = 100으로 인덱싱) ===
with tab3:
    st.markdown("""
    **인덱스 차트**: 조회 기간 시작을 100으로 놓고, 이후 변화를 비교합니다.
    출발점이 같으므로 "어떤 단지가 더 많이 올랐는가"를 직관적으로 비교할 수 있습니다.
    """)

    fig_idx = create_figure(
        title=f"수익률 인덱스 비교 (시작 = 100)",
        xaxis_title="년월", yaxis_title="인덱스",
        hovermode="x unified", xaxis_tickangle=-45,
    )
    fig_idx.add_hline(y=100, line_color="#cbd5e1", line_dash="dot")

    for i, apt in enumerate(selected_apts):
        m = compare_data[apt]["monthly"]
        if m.empty or len(m) < 2:
            continue
        color = CATEGORICAL_10[i % len(CATEGORICAL_10)]
        base = m["median_sqm"].iloc[0]
        if base <= 0:
            continue
        indexed = (m["median_sqm"] / base * 100).round(1)
        fig_idx.add_trace(go.Scatter(
            x=m["ym"], y=indexed,
            mode="lines+markers", name=apt,
            line=dict(color=color, width=2.5),
            marker=dict(size=5),
            hovertemplate="<b>" + apt + "</b><br>%{y:.1f}<extra></extra>",
        ))

    st.plotly_chart(fig_idx, use_container_width=True, key="chart_compare_index")

    # 기간 수익률 요약 바차트
    returns = []
    for apt in selected_apts:
        m = compare_data[apt]["monthly"]
        if m.empty or len(m) < 2:
            continue
        base = m["median_sqm"].iloc[0]
        last = m["median_sqm"].iloc[-1]
        ret = round((last - base) / base * 100, 1) if base > 0 else 0
        returns.append({"단지": apt, "수익률(%)": ret})

    if returns:
        ret_df = pd.DataFrame(returns).sort_values("수익률(%)")
        bar_colors = [COLORS["up"] if r >= 0 else COLORS["down"] for r in ret_df["수익률(%)"]]

        fig_ret = create_figure(
            title="기간 수익률 비교",
            xaxis_title="수익률 (%)", yaxis_title="",
            height=max(200, len(ret_df) * 45),
        )
        fig_ret.add_trace(go.Bar(
            x=ret_df["수익률(%)"], y=ret_df["단지"],
            orientation="h", marker_color=bar_colors,
            text=[f"{v:+.1f}%" for v in ret_df["수익률(%)"]],
            textposition="outside",
        ))
        st.plotly_chart(fig_ret, use_container_width=True, key="chart_compare_return")

# === Tab 4: 상세 테이블 ===
with tab4:
    rows = []
    for apt in selected_apts:
        d = compare_data[apt]
        m = d["monthly"]
        base_sqm = m["median_sqm"].iloc[0] if not m.empty else 0
        last_sqm = m["median_sqm"].iloc[-1] if not m.empty else 0
        ret = round((last_sqm - base_sqm) / base_sqm * 100, 1) if base_sqm > 0 else 0

        # 최근 6개월 모멘텀
        if len(m) >= 6:
            m6 = m["median_sqm"].iloc[-6]
            momentum = round((last_sqm - m6) / m6 * 100, 1) if m6 > 0 else 0
        else:
            momentum = ret

        rows.append({
            "단지": apt,
            "구": d["gu"],
            "동": d["dong"],
            "건축": d["build_year"],
            "m2당가": round(last_sqm, 1),
            "중위가(만원)": int(d["latest_price"]),
            "거래수": d["total_trades"],
            "기간수익률(%)": ret,
            "6M모멘텀(%)": momentum,
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

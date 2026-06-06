import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from config import GU_NAME_TO_CODE
from data_collector import collect_seoul_data
from data_processor import (
    clean_trade_data,
    filter_by_area,
    filter_by_build_year,
    filter_outliers,
    add_area_category,
)
from design_system import (
    show_chart, COLORS, create_figure,
    format_price, format_sqm_price, calc_table_height,
)
from sidebar_filters import render_sidebar_filters


def _pad_x_for_labels(fig, values, frac: float = 0.25):
    """가로 막대 바깥 값 라벨이 잘리지 않도록 x축 여유 공간."""
    vals = [float(v) for v in values if v == v]
    if not vals:
        return
    lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
    pad = ((hi - lo) or 1.0) * frac
    fig.update_xaxes(range=[lo - (pad if min(vals) < 0 else 0.0),
                            hi + (pad if max(vals) > 0 else 0.0)])


render_sidebar_filters()
st.header("단지 랭킹")

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
    st.warning("조회된 데이터가 없습니다.")
    st.stop()

df = clean_trade_data(raw_df)
df = add_area_category(df)
df = filter_by_area(df, selected_area)
df = filter_by_build_year(df, selected_build_year)
df = filter_outliers(df, st.session_state.get("exclude_outliers", True))

if df.empty:
    st.warning("해당 조건의 데이터가 없습니다.")
    st.stop()

# --- 필터 ---
fc1, fc2 = st.columns(2)
top_n = fc1.slider("표시 단지 수", min_value=5, max_value=30, value=10, step=5)
min_trades = fc2.number_input("최소 거래건수", min_value=2, max_value=50, value=3, step=1,
                              help="거래건수가 적은 단지는 중위값이 왜곡될 수 있어 제외합니다.")


# --- 단지별 집계 ---
@st.cache_data(show_spinner=False)
def _build_apt_stats(_df_hash, df_input):
    results = []
    for (gu, dong, apt), g in df_input.groupby(["gu_name", "dong", "apt_name"]):
        tc = len(g)
        if tc < 2:
            continue
        history = g.groupby("ym")["price_per_sqm"].median().sort_index()
        peak_val = history.max()
        peak_ym = history.idxmax()
        current_val = history.iloc[-1]
        drop_pct = round((current_val - peak_val) / peak_val * 100, 1) if peak_val > 0 else 0.0
        med_price = int(g["price"].median())
        med_sqm = round(g["price_per_sqm"].median(), 1)
        med_area = round(g["area"].median(), 1)
        by = int(g["build_year"].median()) if g["build_year"].notna().any() else 0

        results.append({
            "gu": gu, "dong": dong, "apt": apt,
            "area": med_area, "build_year": by,
            "med_price": med_price, "med_sqm": med_sqm,
            "trade_count": tc,
            "peak_sqm": round(peak_val, 1), "peak_ym": peak_ym,
            "current_sqm": round(current_val, 1), "drop_pct": drop_pct,
        })
    return pd.DataFrame(results) if results else pd.DataFrame()


stats = _build_apt_stats(hash(df.to_csv()), df)
if stats.empty:
    st.warning("집계할 단지가 없습니다.")
    st.stop()

stats = stats[stats["trade_count"] >= min_trades]
if stats.empty:
    st.warning(f"거래 {min_trades}건 이상인 단지가 없습니다.")
    st.stop()

st.caption(f"총 {len(stats)}개 단지 | m2당 중위가 기준")


# === 공통 바 차트 헬퍼 ===
def _bar_chart(data, x_col, title, x_label, color, fmt_func, hover_extra=""):
    """가로 막대 차트 + hover 생성."""
    data = data.copy()
    data["label"] = data["apt"] + " (" + data["dong"] + ")"
    fig = create_figure(
        height=max(320, len(data) * 34),
        xaxis_title=x_label, yaxis_title="",
    )
    fig.add_trace(go.Bar(
        x=data[x_col], y=data["label"], orientation="h",
        marker_color=color,
        text=[fmt_func(v) for v in data[x_col]],
        textposition="outside",
        customdata=list(zip(
            data["gu"], data["dong"], data["apt"],
            [format_price(p) for p in data["med_price"]],
            [format_sqm_price(p) for p in data["med_sqm"]],
            data["trade_count"], data["build_year"],
        )),
        hovertemplate=(
            "<b>%{customdata[2]}</b><br>"
            "%{customdata[0]} %{customdata[1]}<br>"
            "중위가: %{customdata[3]}<br>"
            "m2당: %{customdata[4]}<br>"
            "거래: %{customdata[5]}건 / 건축: %{customdata[6]}년"
            + hover_extra +
            "<extra></extra>"
        ),
    ))
    _pad_x_for_labels(fig, data[x_col])
    return fig


# === 탭 구성 ===
tab_price, tab_dong, tab_peak, tab_volume = st.tabs([
    "가격 Top", "동별 대장", "전고점 대비", "거래 활발",
])


# --- 1. 가격 Top ---
with tab_price:
    st.markdown("#### 가장 비싼 단지")
    top_price = stats.sort_values("med_sqm", ascending=False).head(top_n)
    top_price_plot = top_price.sort_values("med_sqm")

    fig = _bar_chart(
        top_price_plot, "med_sqm",
        title="m2당 가격 Top", x_label="m2당 가격 (만원/m2)",
        color=COLORS["primary_dark"],
        fmt_func=lambda v: f"{v:,.0f}",
    )
    show_chart(fig, key="chart_price_top")

    tbl = top_price[["gu", "dong", "apt", "area", "build_year", "med_price", "med_sqm", "trade_count"]].rename(columns={
        "gu": "구", "dong": "동", "apt": "단지명", "area": "면적(m2)",
        "build_year": "건축년도", "med_price": "중위가(만원)",
        "med_sqm": "m2당(만원/m2)", "trade_count": "거래건수",
    })
    st.dataframe(tbl, use_container_width=True, hide_index=True,
                 height=calc_table_height(len(tbl)),
                 column_config={
                     "중위가(만원)": st.column_config.NumberColumn(format="%,d"),
                     "m2당(만원/m2)": st.column_config.NumberColumn(format="%,.1f"),
                 })


# --- 2. 동별 대장 ---
with tab_dong:
    st.markdown("#### 동별 대장 아파트")
    st.caption("각 동에서 m2당 가격이 가장 높은 단지")

    dong_top_n = st.radio("동별 표시", [1, 3, 5], horizontal=True, index=0,
                          format_func=lambda x: f"Top {x}" if x > 1 else "대장 1곳",
                          key="dong_top_n")

    dong_leaders = (
        stats.sort_values("med_sqm", ascending=False)
        .groupby("dong")
        .head(dong_top_n)
        .sort_values(["dong", "med_sqm"], ascending=[True, False])
    )

    # 차트: 동별로 색 구분
    dl_plot = dong_leaders.sort_values("med_sqm").copy()
    dl_plot["label"] = dl_plot["apt"] + " (" + dl_plot["dong"] + ")"
    # 동별 색상 매핑
    dongs = dl_plot["dong"].unique()
    palette = [COLORS["primary_dark"], COLORS["primary"], COLORS["primary_light"],
               COLORS["accent"], "#0891b2", "#16a34a", "#f59e0b", "#ea580c",
               "#db2777", "#6366f1", "#65a30d", "#334155"]
    dong_colors = {d: palette[i % len(palette)] for i, d in enumerate(sorted(dongs))}
    bar_colors = [dong_colors[d] for d in dl_plot["dong"]]

    fig = create_figure(
        height=max(350, len(dl_plot) * 32),
        xaxis_title="m2당 가격 (만원/m2)", yaxis_title="",
    )
    fig.add_trace(go.Bar(
        x=dl_plot["med_sqm"], y=dl_plot["label"], orientation="h",
        marker_color=bar_colors,
        text=[f"{v:,.0f}" for v in dl_plot["med_sqm"]],
        textposition="outside",
        customdata=list(zip(
            dl_plot["gu"], dl_plot["dong"], dl_plot["apt"],
            [format_price(p) for p in dl_plot["med_price"]],
            dl_plot["trade_count"], dl_plot["build_year"],
        )),
        hovertemplate=(
            "<b>%{customdata[2]}</b><br>"
            "%{customdata[0]} %{customdata[1]}<br>"
            "m2당: %{x:,.0f}만원/m2<br>"
            "중위가: %{customdata[3]}<br>"
            "거래: %{customdata[4]}건 / 건축: %{customdata[5]}년"
            "<extra></extra>"
        ),
    ))
    _pad_x_for_labels(fig, dl_plot["med_sqm"])
    show_chart(fig, key="chart_dong_leaders")

    tbl2 = dong_leaders[["gu", "dong", "apt", "area", "build_year", "med_price", "med_sqm", "trade_count"]].rename(columns={
        "gu": "구", "dong": "동", "apt": "단지명", "area": "면적(m2)",
        "build_year": "건축년도", "med_price": "중위가(만원)",
        "med_sqm": "m2당(만원/m2)", "trade_count": "거래건수",
    })
    st.dataframe(tbl2, use_container_width=True, hide_index=True,
                 height=calc_table_height(len(tbl2)),
                 column_config={
                     "중위가(만원)": st.column_config.NumberColumn(format="%,d"),
                     "m2당(만원/m2)": st.column_config.NumberColumn(format="%,.1f"),
                 })


# --- 3. 전고점 대비 낙폭 ---
with tab_peak:
    st.markdown("#### 전고점 대비 낙폭")
    st.caption("m2당 가격 기준, 고점 대비 현재 하락률이 큰 단지")

    peak_down = stats[stats["drop_pct"] < -1].sort_values("drop_pct").head(top_n)
    peak_up = stats[stats["drop_pct"] > 1].sort_values("drop_pct", ascending=False).head(top_n)

    if not peak_down.empty:
        pd_plot = peak_down.sort_values("drop_pct", ascending=False).copy()
        pd_plot["label"] = pd_plot["apt"] + " (" + pd_plot["dong"] + ")"

        fig = create_figure(
            height=max(320, len(pd_plot) * 34),
            xaxis_title="전고점 대비 (%)", yaxis_title="",
        )
        fig.add_trace(go.Bar(
            x=pd_plot["drop_pct"], y=pd_plot["label"], orientation="h",
            marker_color=COLORS["down"],
            text=[f"{v:.1f}%" for v in pd_plot["drop_pct"]],
            textposition="outside",
            customdata=list(zip(
                pd_plot["gu"], pd_plot["dong"], pd_plot["apt"],
                [format_sqm_price(p) for p in pd_plot["peak_sqm"]],
                pd_plot["peak_ym"],
                [format_sqm_price(p) for p in pd_plot["current_sqm"]],
            )),
            hovertemplate=(
                "<b>%{customdata[2]}</b><br>"
                "%{customdata[0]} %{customdata[1]}<br>"
                "전고점: %{customdata[3]} (%{customdata[4]})<br>"
                "현재: %{customdata[5]}<extra></extra>"
            ),
        ))
        _pad_x_for_labels(fig, pd_plot["drop_pct"])
        show_chart(fig, key="chart_peak_drop")

        tbl3 = peak_down[["gu", "dong", "apt", "area", "peak_sqm", "peak_ym", "current_sqm", "drop_pct"]].rename(columns={
            "gu": "구", "dong": "동", "apt": "단지명", "area": "면적(m2)",
            "peak_sqm": "전고점 m2당가", "peak_ym": "고점시기",
            "current_sqm": "현재 m2당가", "drop_pct": "전고점 대비(%)",
        })
        st.dataframe(tbl3, use_container_width=True, hide_index=True,
                     height=calc_table_height(len(tbl3)),
                     column_config={
                         "전고점 m2당가": st.column_config.NumberColumn(format="%,.1f"),
                         "현재 m2당가": st.column_config.NumberColumn(format="%,.1f"),
                         "전고점 대비(%)": st.column_config.NumberColumn(format="%+.1f%%"),
                     })
    else:
        st.info("전고점보다 하락한 단지가 없습니다.")

    if not peak_up.empty:
        st.markdown("##### 전고점 경신 단지")
        pu_plot = peak_up.sort_values("drop_pct").copy()
        pu_plot["label"] = pu_plot["apt"] + " (" + pu_plot["dong"] + ")"
        fig2 = create_figure(
            height=max(280, len(pu_plot) * 34),
            xaxis_title="전고점 대비 (%)", yaxis_title="",
        )
        fig2.add_trace(go.Bar(
            x=pu_plot["drop_pct"], y=pu_plot["label"], orientation="h",
            marker_color=COLORS["primary"],
            text=[f"+{v:.1f}%" for v in pu_plot["drop_pct"]],
            textposition="outside",
        ))
        _pad_x_for_labels(fig2, pu_plot["drop_pct"])
        show_chart(fig2, key="chart_peak_new_high")


# --- 4. 거래 활발 ---
with tab_volume:
    st.markdown("#### 거래량 Top")
    st.caption("조회 기간 내 거래가 가장 많은 단지 — 시장의 관심이 집중되는 곳")

    top_vol = stats.sort_values("trade_count", ascending=False).head(top_n)
    tv_plot = top_vol.sort_values("trade_count").copy()

    fig = _bar_chart(
        tv_plot, "trade_count",
        title="거래량 Top", x_label="거래건수",
        color=COLORS["up"],
        fmt_func=lambda v: f"{int(v)}건",
    )
    show_chart(fig, key="chart_vol_top")

    tbl4 = top_vol[["gu", "dong", "apt", "area", "build_year", "med_price", "med_sqm", "trade_count"]].rename(columns={
        "gu": "구", "dong": "동", "apt": "단지명", "area": "면적(m2)",
        "build_year": "건축년도", "med_price": "중위가(만원)",
        "med_sqm": "m2당(만원/m2)", "trade_count": "거래건수",
    })
    st.dataframe(tbl4, use_container_width=True, hide_index=True,
                 height=calc_table_height(len(tbl4)),
                 column_config={
                     "중위가(만원)": st.column_config.NumberColumn(format="%,d"),
                     "m2당(만원/m2)": st.column_config.NumberColumn(format="%,.1f"),
                 })

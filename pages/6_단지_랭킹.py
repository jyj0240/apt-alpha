import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from config import GU_NAME_TO_CODE, AREA_CATEGORIES
from data_collector import collect_seoul_data
from data_processor import (
    clean_trade_data,
    filter_by_area,
    filter_by_build_year,
    filter_outliers,
    add_area_category,
    calc_apt_peak_drop,
)
from design_system import COLORS, apply_theme, create_figure, format_price, format_sqm_price, calc_table_height
from sidebar_filters import render_sidebar_filters

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


# --- 단지별 대표 면적대 계산 ---
def _get_apt_dominant_area(df: pd.DataFrame) -> dict:
    """각 단지의 최빈 면적대를 반환한다."""
    result = {}
    for (gu, dong, apt), group in df.groupby(["gu_name", "dong", "apt_name"]):
        mode = group["area_category"].mode()
        result[(gu, dong, apt)] = mode.iloc[0] if not mode.empty else "전체"
    return result


apt_area_map = _get_apt_dominant_area(df)


# --- m2당 가격 기준 기간 변화율 계산 ---
def calc_apt_period_change(df: pd.DataFrame) -> pd.DataFrame:
    """단지별 기간 내 m2당 단가 시작 vs 종료 변화율. 면적대 정보 포함."""
    results = []
    for (gu, dong, apt_name), group in df.groupby(["gu_name", "dong", "apt_name"]):
        history = (
            group.groupby("ym")
            .agg(
                median_price=("price", "median"),
                median_sqm=("price_per_sqm", "median"),
            )
            .reset_index()
            .sort_values("ym")
        )
        if len(history) < 2:
            continue
        first_sqm = history["median_sqm"].iloc[0]
        last_sqm = history["median_sqm"].iloc[-1]
        first_price = history["median_price"].iloc[0]
        last_price = history["median_price"].iloc[-1]
        trade_count = len(group)
        median_area = round(group["area"].median(), 1)
        dominant_area_cat = apt_area_map.get((gu, dong, apt_name), "전체")

        change_pct = round((last_sqm - first_sqm) / first_sqm * 100, 1) if first_sqm > 0 else 0.0
        results.append({
            "구": gu, "동": dong, "단지명": apt_name,
            "면적대": dominant_area_cat,
            "대표면적(m2)": median_area,
            "시작 m2당가": int(first_sqm),
            "최근 m2당가": int(last_sqm),
            "시작 중위가": int(first_price),
            "최근 중위가": int(last_price),
            "m2당 상승률(%)": change_pct,
            "거래건수": trade_count,
        })
    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results).sort_values("m2당 상승률(%)", ascending=False)


ranking_df = calc_apt_period_change(df)

if ranking_df.empty:
    st.warning("기간 내 2개월 이상 거래가 있는 단지가 없습니다.")
    st.stop()

# --- 필터 컨트롤 ---
fc1, fc2 = st.columns(2)
top_n = fc1.slider("상위/하위 단지 수", min_value=5, max_value=30, value=10, step=5)
min_trades = fc2.number_input("최소 거래건수", min_value=2, max_value=50, value=3, step=1,
                              help="노이즈 제거를 위해 거래건수가 적은 단지를 필터링합니다.")

area_options_ranking = ["전체 (면적대 무관)"] + sorted(ranking_df["면적대"].unique().tolist())
compare_area = st.selectbox("비교 면적대 그룹", area_options_ranking,
                            help="같은 면적대끼리 비교합니다.")

ranking_df = ranking_df[ranking_df["거래건수"] >= min_trades]
if compare_area != "전체 (면적대 무관)":
    ranking_df = ranking_df[ranking_df["면적대"] == compare_area]

if ranking_df.empty:
    st.warning(f"해당 조건의 단지가 없습니다.")
    st.stop()

st.caption(f"m2당 가격(만원/m2) 기준 비교 | 총 {len(ranking_df)}개 단지")

tab_up, tab_down, tab_peak = st.tabs(["상승 Top", "하락 Top", "전고점 대비 낙폭"])

# --- 상승 Top ---
with tab_up:
    top_up = ranking_df.head(top_n).copy()
    st.subheader(f"m2당 상승률 Top {top_n}")

    top_up_sorted = top_up.sort_values("m2당 상승률(%)")
    top_up_sorted["label"] = top_up_sorted["단지명"] + " (" + top_up_sorted["대표면적(m2)"].astype(str) + "m2)"

    fig = create_figure(
        height=max(350, top_n * 38),
        xaxis_title="m2당 상승률 (%)",
        yaxis_title="",
    )
    fig.add_trace(go.Bar(
        x=top_up_sorted["m2당 상승률(%)"],
        y=top_up_sorted["label"],
        orientation="h",
        marker=dict(
            color=top_up_sorted["m2당 상승률(%)"],
            colorscale=[[0, COLORS["primary_light"]], [1, COLORS["primary_dark"]]],
        ),
        text=[f"{v:+.1f}%" for v in top_up_sorted["m2당 상승률(%)"]],
        textposition="outside",
        customdata=list(zip(
            top_up_sorted["구"], top_up_sorted["동"], top_up_sorted["면적대"],
            [format_sqm_price(p) for p in top_up_sorted["시작 m2당가"]],
            [format_sqm_price(p) for p in top_up_sorted["최근 m2당가"]],
            top_up_sorted["거래건수"],
        )),
        hovertemplate=(
            "<b>%{customdata[0]} %{customdata[1]}</b><br>"
            "면적대: %{customdata[2]}<br>"
            "시작: %{customdata[3]} -> 최근: %{customdata[4]}<br>"
            "거래: %{customdata[5]}건<extra></extra>"
        ),
    ))
    st.plotly_chart(fig, use_container_width=True, key="chart_top_up")

    _up_tbl = top_up[["구", "동", "단지명", "면적대", "대표면적(m2)", "시작 m2당가", "최근 m2당가", "m2당 상승률(%)", "거래건수"]]
    st.dataframe(
        _up_tbl,
        column_config={
            "시작 m2당가": st.column_config.NumberColumn("시작 m2당가", format="%,d만원/m2"),
            "최근 m2당가": st.column_config.NumberColumn("최근 m2당가", format="%,d만원/m2"),
            "m2당 상승률(%)": st.column_config.NumberColumn("상승률(%)", format="%+.1f%%"),
        },
        use_container_width=True, hide_index=True,
        height=calc_table_height(len(_up_tbl)),
    )

# --- 하락 Top ---
with tab_down:
    top_down = ranking_df.tail(top_n).sort_values("m2당 상승률(%)").copy()
    st.subheader(f"m2당 하락률 Top {top_n}")

    top_down_sorted = top_down.sort_values("m2당 상승률(%)", ascending=False)
    top_down_sorted["label"] = top_down_sorted["단지명"] + " (" + top_down_sorted["대표면적(m2)"].astype(str) + "m2)"

    fig2 = create_figure(
        height=max(350, top_n * 38),
        xaxis_title="m2당 상승률 (%)",
        yaxis_title="",
    )
    fig2.add_trace(go.Bar(
        x=top_down_sorted["m2당 상승률(%)"],
        y=top_down_sorted["label"],
        orientation="h",
        marker=dict(
            color=top_down_sorted["m2당 상승률(%)"],
            colorscale=[[0, COLORS["down"]], [1, "#fecaca"]],
        ),
        text=[f"{v:+.1f}%" for v in top_down_sorted["m2당 상승률(%)"]],
        textposition="outside",
        customdata=list(zip(
            top_down_sorted["구"], top_down_sorted["동"], top_down_sorted["면적대"],
            [format_sqm_price(p) for p in top_down_sorted["시작 m2당가"]],
            [format_sqm_price(p) for p in top_down_sorted["최근 m2당가"]],
            top_down_sorted["거래건수"],
        )),
        hovertemplate=(
            "<b>%{customdata[0]} %{customdata[1]}</b><br>"
            "면적대: %{customdata[2]}<br>"
            "시작: %{customdata[3]} -> 최근: %{customdata[4]}<br>"
            "거래: %{customdata[5]}건<extra></extra>"
        ),
    ))
    st.plotly_chart(fig2, use_container_width=True, key="chart_top_down")

    _down_tbl = top_down[["구", "동", "단지명", "면적대", "대표면적(m2)", "시작 m2당가", "최근 m2당가", "m2당 상승률(%)", "거래건수"]]
    st.dataframe(
        _down_tbl,
        column_config={
            "시작 m2당가": st.column_config.NumberColumn("시작 m2당가", format="%,d만원/m2"),
            "최근 m2당가": st.column_config.NumberColumn("최근 m2당가", format="%,d만원/m2"),
            "m2당 상승률(%)": st.column_config.NumberColumn("상승률(%)", format="%+.1f%%"),
        },
        use_container_width=True, hide_index=True,
        height=calc_table_height(len(_down_tbl)),
    )

# --- 전고점 대비 낙폭 ---
with tab_peak:
    st.subheader(f"전고점 대비 낙폭 Top {top_n}")
    st.caption("m2당 가격 기준 전고점 대비 현재 가격 변화율")

    # m2당 가격 기준 전고점 계산
    peak_results = []
    for (gu, dong, apt_name), group in df.groupby(["gu_name", "dong", "apt_name"]):
        if len(group) < 2:
            continue
        history = (
            group.groupby("ym")["price_per_sqm"]
            .median()
            .reset_index()
            .sort_values("ym")
        )
        if len(history) < 2:
            continue
        peak_idx = history["price_per_sqm"].idxmax()
        peak_val = history.loc[peak_idx, "price_per_sqm"]
        peak_ym = history.loc[peak_idx, "ym"]
        current_val = history["price_per_sqm"].iloc[-1]
        drop_pct = round((current_val - peak_val) / peak_val * 100, 1) if peak_val > 0 else 0.0
        median_area = round(group["area"].median(), 1)
        dominant_cat = apt_area_map.get((gu, dong, apt_name), "전체")

        if len(group) >= min_trades:
            peak_results.append({
                "gu_name": gu, "dong": dong, "apt_name": apt_name,
                "면적대": dominant_cat, "대표면적": median_area,
                "peak_sqm": int(peak_val), "peak_ym": peak_ym,
                "current_sqm": int(current_val),
                "drop_pct": drop_pct,
            })

    peak_df = pd.DataFrame(peak_results).sort_values("drop_pct") if peak_results else pd.DataFrame()

    if compare_area != "전체 (면적대 무관)" and not peak_df.empty:
        peak_df = peak_df[peak_df["면적대"] == compare_area]

    if peak_df.empty:
        st.info("전고점 계산에 충분한 데이터가 없습니다.")
    else:
        peak_down = peak_df[peak_df["drop_pct"] < 0].head(top_n).copy()
        peak_up = peak_df[peak_df["drop_pct"] >= 0].sort_values("drop_pct", ascending=False).head(top_n).copy()

        if not peak_down.empty:
            peak_down["label"] = peak_down["apt_name"] + " (" + peak_down["대표면적"].astype(str) + "m2)"

            fig3 = create_figure(
                height=max(350, len(peak_down) * 38),
                xaxis_title="전고점 대비 (%)",
                yaxis_title="",
            )
            fig3.add_trace(go.Bar(
                x=peak_down.sort_values("drop_pct", ascending=False)["drop_pct"],
                y=peak_down.sort_values("drop_pct", ascending=False)["label"],
                orientation="h",
                marker=dict(color=COLORS["down"]),
                text=[f"{v:.1f}%" for v in peak_down.sort_values("drop_pct", ascending=False)["drop_pct"]],
                textposition="outside",
                customdata=list(zip(
                    peak_down.sort_values("drop_pct", ascending=False)["gu_name"],
                    peak_down.sort_values("drop_pct", ascending=False)["dong"],
                    peak_down.sort_values("drop_pct", ascending=False)["면적대"],
                    [format_sqm_price(p) for p in peak_down.sort_values("drop_pct", ascending=False)["peak_sqm"]],
                    peak_down.sort_values("drop_pct", ascending=False)["peak_ym"],
                    [format_sqm_price(p) for p in peak_down.sort_values("drop_pct", ascending=False)["current_sqm"]],
                )),
                hovertemplate=(
                    "<b>%{customdata[0]} %{customdata[1]}</b><br>"
                    "면적대: %{customdata[2]}<br>"
                    "전고점: %{customdata[3]} (%{customdata[4]})<br>"
                    "현재: %{customdata[5]}<extra></extra>"
                ),
            ))
            st.plotly_chart(fig3, use_container_width=True, key="chart_peak_drop")

            _peak_tbl = peak_down[["gu_name", "dong", "apt_name", "면적대", "대표면적", "peak_sqm", "peak_ym", "current_sqm", "drop_pct"]].rename(columns={
                    "gu_name": "구", "dong": "동", "apt_name": "단지명",
                    "peak_sqm": "전고점 m2당가", "peak_ym": "전고점 시기",
                    "current_sqm": "현재 m2당가", "drop_pct": "전고점 대비(%)",
                })
            st.dataframe(
                _peak_tbl,
                column_config={
                    "전고점 m2당가": st.column_config.NumberColumn(format="%,d만원/m2"),
                    "현재 m2당가": st.column_config.NumberColumn(format="%,d만원/m2"),
                    "전고점 대비(%)": st.column_config.NumberColumn(format="%+.1f%%"),
                },
                use_container_width=True, hide_index=True,
                height=calc_table_height(len(_peak_tbl)),
            )
        else:
            st.info("전고점보다 하락한 단지가 없습니다.")

        if not peak_up.empty:
            st.markdown("##### 전고점 경신 단지")
            peak_up["label"] = peak_up["apt_name"] + " (" + peak_up["대표면적"].astype(str) + "m2)"
            fig4 = create_figure(
                height=max(300, len(peak_up) * 38),
                xaxis_title="전고점 대비 (%)",
                yaxis_title="",
            )
            fig4.add_trace(go.Bar(
                x=peak_up.sort_values("drop_pct")["drop_pct"],
                y=peak_up.sort_values("drop_pct")["label"],
                orientation="h",
                marker=dict(color=COLORS["primary"]),
                text=[f"+{v:.1f}%" for v in peak_up.sort_values("drop_pct")["drop_pct"]],
                textposition="outside",
            ))
            st.plotly_chart(fig4, use_container_width=True, key="chart_peak_new_high")

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from config import GU_NAME_TO_CODE
from data_collector import collect_seoul_data, collect_seoul_rent_data
from data_processor import (
    clean_trade_data,
    clean_rent_data,
    filter_by_area,
    filter_by_build_year,
    filter_outliers,
    add_area_category,
    aggregate_by_apt,
    get_apt_price_history,
    calc_period_change,
    aggregate_by_gu_month,
    calc_apt_peak_drop,
)
from design_system import (
    COLORS, CATEGORICAL_10, apply_theme, create_figure,
    format_price, format_pct, add_last_point_label, add_reference_line,
    calc_table_height,
)
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()
st.header("아파트 단지 분석")

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
    gu_codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
    return collect_seoul_data(s_ym, e_ym, gu_codes)


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
    st.warning("해당 면적대 데이터가 없습니다.")
    st.stop()

# --- 1단계: 구 → 동 → 단지 → 면적 선택 ---
sel_row1 = st.columns(4)

with sel_row1[0]:
    gu_options = sorted(df["gu_name"].dropna().unique())
    selected_gu = st.selectbox("구 선택", gu_options)

df_gu = df[df["gu_name"] == selected_gu]

with sel_row1[1]:
    dong_options = ["전체"] + sorted(df_gu["dong"].dropna().unique())
    selected_dong = st.selectbox("동 선택", dong_options)

df_dong = df_gu if selected_dong == "전체" else df_gu[df_gu["dong"] == selected_dong]

with sel_row1[2]:
    apt_counts = df_dong["apt_name"].value_counts()
    apt_options = apt_counts.index.tolist()
    selected_apt = st.selectbox("단지 선택", apt_options)

df_apt_all = df_dong[df_dong["apt_name"] == selected_apt]

with sel_row1[3]:
    # 해당 단지의 실제 전용면적 목록 (반올림해서 그룹화)
    if not df_apt_all.empty:
        areas = df_apt_all["area"].dropna().round(0).astype(int)
        area_counts = areas.value_counts().sort_index()
        area_labels = {0: "전체"}
        for a in area_counts.index:
            area_labels[a] = f"{a}m2 ({area_counts[a]}건)"
        area_keys = [0] + list(area_counts.index)
        selected_apt_area = st.selectbox(
            "전용면적", area_keys,
            format_func=lambda x: area_labels.get(x, str(x)),
        )
    else:
        selected_apt_area = 0

# 면적 필터 적용
if selected_apt_area == 0:
    df_apt = df_apt_all
else:
    df_apt = df_apt_all[df_apt_all["area"].round(0).astype(int) == selected_apt_area]

if df_apt.empty:
    st.warning("해당 단지의 거래 데이터가 없습니다.")
    st.stop()

st.divider()

# --- KPI 카드 ---
history = get_apt_price_history(df_apt, selected_apt)

latest_price = history["median_price"].iloc[-1] if not history.empty else 0
latest_sqm = history["median_price_per_sqm"].iloc[-1] if not history.empty else 0
total_trades = int(df_apt["price"].count())

# 기간 상승률
if len(history) >= 2:
    first_p = history["median_price"].iloc[0]
    last_p = history["median_price"].iloc[-1]
    change_pct = round((last_p - first_p) / first_p * 100, 1) if first_p > 0 else 0.0
else:
    change_pct = 0.0

# 구 중위가 대비 프리미엄
gu_median = df_gu["price"].median()
premium_pct = round((latest_price - gu_median) / gu_median * 100, 1) if gu_median > 0 else 0.0

build_year = int(df_apt["build_year"].median()) if df_apt["build_year"].notna().any() else 0
building_age = (2026 - build_year) if build_year > 0 else 0

# 전고점 대비 하락률
peak_drop_df = calc_apt_peak_drop(df_apt)
if not peak_drop_df.empty:
    row = peak_drop_df.iloc[0]
    peak_price = row["peak_price"]
    peak_ym = row["peak_ym"]
    drop_pct = row["drop_pct"]
else:
    peak_price, peak_ym, drop_pct = latest_price, "-", 0.0

row1 = st.columns(3)
row1[0].metric("최근 중위가", f"{latest_price:,.0f}만원")
row1[1].metric("m2당 가격", f"{latest_sqm:,.1f}만원/m2")
row1[2].metric("기간 상승률", f"{change_pct:+.1f}%")
row2 = st.columns(3)
row2[0].metric(f"{selected_gu} 대비", f"{premium_pct:+.1f}%")
row2[1].metric(
    "전고점 대비",
    f"{drop_pct:+.1f}%",
    delta=f"전고점 {peak_ym} / {peak_price:,.0f}만원",
    delta_color="off",
)
row2[2].metric("건축연도", f"{build_year}년 ({building_age}년)")

st.divider()

# --- 차트 영역 ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "가격 추이", "면적별 분포", "층수 vs 가격", "동네 단지 비교", "실거래 내역", "매매-전세 갭"
])

# 탭1: 월별 가격 추이
with tab1:
    if not history.empty and len(history) > 1:
        formatted_prices = [format_price(p) for p in history["median_price"]]
        fig = create_figure(
            title=f"{selected_apt} 월별 중위 거래가",
            xaxis_title="년월", yaxis_title="중위가격 (만원)",
            xaxis_tickangle=-45,
        )
        fig.add_trace(go.Scatter(
            x=history["ym"], y=history["median_price"],
            mode="lines+markers",
            line=dict(color=COLORS["primary"], width=2.5),
            marker=dict(size=6),
            customdata=list(zip(formatted_prices)),
            hovertemplate="%{x}<br>%{customdata[0]}<extra></extra>",
            name="중위가격",
        ))

        # 전고점 마커 annotation
        peak_idx = history["median_price"].idxmax()
        peak_row = history.loc[peak_idx]
        fig.add_annotation(
            x=peak_row["ym"], y=peak_row["median_price"],
            text=f"전고점 {format_price(peak_row['median_price'])}",
            showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
            arrowcolor=COLORS["down"], font=dict(size=10, color=COLORS["down"]),
            ax=0, ay=-35,
        )

        # 마지막 포인트 레이블
        add_last_point_label(
            fig, history["ym"].tolist(), history["median_price"].tolist(),
            format_price(history["median_price"].iloc[-1]),
            color=COLORS["primary"],
        )

        # 기간 변화율 annotation
        if change_pct != 0:
            fig.add_annotation(
                xref="paper", yref="paper", x=0.02, y=0.98,
                text=f"기간 변화: {format_pct(change_pct)}",
                showarrow=False,
                font=dict(size=12, color=COLORS["up"] if change_pct > 0 else COLORS["down"], weight="bold"),
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor=COLORS["border"],
                borderwidth=1, borderpad=6,
            )

        st.plotly_chart(fig, use_container_width=True, key="chart_apt_trend")

        fig2 = create_figure(
            title="월별 거래건수",
            xaxis_title="년월", yaxis_title="거래건수",
            xaxis_tickangle=-45,
        )
        fig2.add_trace(go.Bar(
            x=history["ym"], y=history["trade_count"],
            marker_color=COLORS["primary_light"],
            hovertemplate="%{x}<br>%{y}건<extra></extra>",
            name="거래건수",
        ))
        st.plotly_chart(fig2, use_container_width=True, key="chart_apt_volume")
    else:
        st.info("추이 차트를 그리기에 데이터가 부족합니다 (최소 2개월 필요).")

# 탭2: 면적별 가격 분포
with tab2:
    area_groups = df_apt.copy()
    area_groups["면적대"] = area_groups["area_category"]

    if not area_groups.empty:
        fig = px.box(
            area_groups,
            x="면적대", y="price",
            color="면적대",
            title=f"{selected_apt} 면적대별 가격 분포",
            labels={"price": "거래가격 (만원)"},
            points="all",
        )
        st.plotly_chart(fig, use_container_width=True, key="chart_area_box")

        # 면적 vs 가격 산점도
        fig2 = px.scatter(
            df_apt,
            x="area", y="price",
            color="area_category",
            hover_data=["floor", "ym"],
            title="전용면적 vs 거래가격",
            labels={"area": "전용면적 (m2)", "price": "거래가격 (만원)", "area_category": "면적대"},
            opacity=0.7,
        )
        st.plotly_chart(fig2, use_container_width=True, key="chart_area_scatter")

# 탭3: 층수 vs 가격
with tab3:
    if not df_apt.empty:
        floor_data = df_apt.dropna(subset=["floor", "price"]).copy()
        formatted_p = [format_price(p) for p in floor_data["price"]]
        fig = px.scatter(
            floor_data,
            x="floor", y="price",
            color="area_category",
            color_discrete_sequence=CATEGORICAL_10,
            title=f"{selected_apt} 층수별 거래가격",
            labels={"floor": "층", "price": "거래가격 (만원)", "area_category": "면적대"},
            trendline="ols",
            opacity=0.7,
        )
        fig.update_traces(
            selector=dict(mode="markers"),
            hovertemplate="%{x}층 / %{customdata[0]}m2<br>%{customdata[1]}<extra></extra>",
            customdata=list(zip(
                floor_data["area"].round(1).astype(str),
                formatted_p,
            )),
        )
        apply_theme(fig)
        st.plotly_chart(fig, use_container_width=True, key="chart_floor_price")

        avg_by_floor = (
            floor_data
            .groupby(floor_data["floor"].astype(int) // 5 * 5)["price"]
            .median()
            .reset_index()
        )
        avg_by_floor.columns = ["층 구간", "중위가격"]
        avg_by_floor["층 구간"] = avg_by_floor["층 구간"].apply(lambda x: f"{x}~{x+4}층")

        # 층별 프리미엄 해석
        if len(avg_by_floor) >= 2:
            price_per_floor = (avg_by_floor["중위가격"].iloc[-1] - avg_by_floor["중위가격"].iloc[0])
            floor_diff = (int(avg_by_floor["층 구간"].iloc[-1].split("~")[0]) -
                          int(avg_by_floor["층 구간"].iloc[0].split("~")[0]))
            if floor_diff > 0:
                per_floor_premium = int(price_per_floor / floor_diff)
                st.info(f"층당 약 {per_floor_premium:+,}만원 프리미엄 (최저 구간 → 최고 구간 기준)")

        st.markdown("**층 구간별 중위가격**")
        st.dataframe(
            avg_by_floor,
            column_config={
                "층 구간": st.column_config.TextColumn("층 구간"),
                "중위가격": st.column_config.NumberColumn("중위가격", format="%,.0f만원"),
            },
            use_container_width=True, hide_index=True,
        )

# 탭4: 동네 단지 비교
with tab4:
    # 같은 면적대끼리 비교
    if selected_apt_area == 0:
        df_dong_compare = df_dong
        compare_label = "전체 면적"
    else:
        df_dong_compare = df_dong[df_dong["area"].round(0).astype(int) == selected_apt_area]
        compare_label = f"{selected_apt_area}m2"
    apt_summary = aggregate_by_apt(df_dong_compare)
    if not apt_summary.empty:
        apt_summary_sorted = apt_summary.sort_values("median_price_per_sqm", ascending=True)

        fig = px.bar(
            apt_summary_sorted,
            x="median_price_per_sqm", y="apt_name",
            orientation="h",
            title=f"{selected_dong} 단지별 m2당 가격 비교 ({compare_label})",
            labels={"median_price_per_sqm": "m2당 가격 (만원/m2)", "apt_name": "단지"},
            color="median_price_per_sqm",
            color_continuous_scale="Blues",
        )
        # 선택 단지 강조
        colors = [
            "#1d4ed8" if apt == selected_apt else "#93c5fd"
            for apt in apt_summary_sorted["apt_name"]
        ]
        fig.update_traces(marker_color=colors)
        fig.update_layout(
            height=max(300, len(apt_summary) * 30),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True, key="chart_dong_compare")

        # 비교 테이블
        display = apt_summary_sorted.sort_values("median_price_per_sqm", ascending=False).rename(columns={
            "apt_name": "단지명",
            "median_price": "중위가격(만원)",
            "median_price_per_sqm": "m2당(만원/m2)",
            "trade_count": "거래건수",
            "avg_build_year": "평균건축년도",
        })
        display["선택"] = display["단지명"].apply(lambda x: "★" if x == selected_apt else "")
        _apt_display = display[["선택", "단지명", "중위가격(만원)", "m2당(만원/m2)", "거래건수", "평균건축년도"]]
        st.dataframe(
            _apt_display,
            use_container_width=True,
            hide_index=True,
            height=calc_table_height(len(_apt_display)),
        )

# 탭5: 실거래 내역
with tab5:
    display_cols = ["ym", "area", "floor", "price", "price_per_sqm", "date"]
    available = [c for c in display_cols if c in df_apt.columns]
    recent = df_apt[available].sort_values("date", ascending=False).head(200)
    recent = recent.rename(columns={
        "ym": "년월", "area": "전용면적(m2)", "floor": "층",
        "price": "거래가격(만원)", "price_per_sqm": "m2당(만원/m2)", "date": "거래일",
    })
    st.markdown(f"**최근 거래 내역** (최대 200건, 전체 {len(df_apt)}건)")
    st.dataframe(recent, use_container_width=True, hide_index=True, height=calc_table_height(len(recent), max_h=600))

# 탭6: 매매-전세 갭 추이
with tab6:
    st.markdown("#### 매매 중위가 vs 전세 중위보증금 비교")
    st.caption("같은 단지·같은 면적대의 매매가와 전세 보증금을 월별로 비교합니다.")

    @st.cache_data(show_spinner="전월세 데이터 수집 중...")
    def get_rent_for_gap(gus, s_ym, e_ym):
        codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
        return collect_seoul_rent_data(s_ym, e_ym, codes)

    raw_rent = get_rent_for_gap(tuple(selected_gus), start_ym, end_ym)

    if raw_rent.empty:
        st.warning("전월세 데이터를 불러올 수 없습니다. API 활용신청이 필요할 수 있습니다.")
    else:
        rent_clean = clean_rent_data(raw_rent)
        # 선택 단지의 전세 데이터만 추출
        apt_jeonse = rent_clean[
            (rent_clean["apt_name"] == selected_apt) & (rent_clean["rent_type"] == "전세")
        ]

        if apt_jeonse.empty:
            st.info(f"'{selected_apt}' 단지의 전세 거래 데이터가 없습니다.")
        else:
            # 월별 집계
            trade_monthly = (
                df_apt.groupby("ym")["price"].median().reset_index()
                .rename(columns={"price": "매매 중위가"})
            )
            jeonse_monthly = (
                apt_jeonse.groupby("ym")["deposit"].median().reset_index()
                .rename(columns={"deposit": "전세 중위보증금"})
            )

            gap_df = trade_monthly.merge(jeonse_monthly, on="ym", how="inner").sort_values("ym")
            gap_df["갭(매매-전세)"] = gap_df["매매 중위가"] - gap_df["전세 중위보증금"]
            gap_df["전세가율(%)"] = (gap_df["전세 중위보증금"] / gap_df["매매 중위가"] * 100).round(1)

            if gap_df.empty:
                st.info("매매와 전세 데이터가 겹치는 기간이 없습니다.")
            else:
                # KPI
                latest = gap_df.iloc[-1]
                kc1, kc2, kc3 = st.columns(3)
                kc1.metric("최근 매매 중위가", f"{latest['매매 중위가']:,.0f}만원")
                kc2.metric("최근 전세 중위보증금", f"{latest['전세 중위보증금']:,.0f}만원")
                kc3.metric(
                    "최근 갭",
                    f"{latest['갭(매매-전세)']:,.0f}만원",
                    delta=f"전세가율 {latest['전세가율(%)']:.1f}%",
                    delta_color="off",
                )

                st.divider()

                # 듀얼 라인 차트
                fig_gap = go.Figure()
                fig_gap.add_trace(go.Scatter(
                    x=gap_df["ym"], y=gap_df["매매 중위가"],
                    mode="lines+markers", name="매매 중위가",
                    line=dict(color="#2563eb", width=2.5),
                ))
                fig_gap.add_trace(go.Scatter(
                    x=gap_df["ym"], y=gap_df["전세 중위보증금"],
                    mode="lines+markers", name="전세 중위보증금",
                    line=dict(color="#16a34a", width=2.5),
                ))
                # 갭 영역 fill
                fig_gap.add_trace(go.Scatter(
                    x=list(gap_df["ym"]) + list(gap_df["ym"])[::-1],
                    y=list(gap_df["매매 중위가"]) + list(gap_df["전세 중위보증금"])[::-1],
                    fill="toself",
                    fillcolor="rgba(37,99,235,0.08)",
                    line=dict(color="rgba(255,255,255,0)"),
                    hoverinfo="skip",
                    name="갭 영역",
                    showlegend=False,
                ))
                fig_gap.update_layout(
                    title=f"{selected_apt} 매매 vs 전세 추이",
                    xaxis_title="년월",
                    yaxis_title="금액 (만원)",
                    hovermode="x unified",
                    xaxis_tickangle=-45,
                    template="plotly_white",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_gap, use_container_width=True, key="chart_gap_line")

                # 갭 바차트
                fig_bar = px.bar(
                    gap_df, x="ym", y="갭(매매-전세)",
                    title="월별 매매-전세 갭 (만원)",
                    labels={"ym": "년월", "갭(매매-전세)": "갭 (만원)"},
                    color="갭(매매-전세)",
                    color_continuous_scale=["#16a34a", "#fbbf24", "#ef4444"],
                )
                fig_bar.update_layout(
                    xaxis_tickangle=-45,
                    coloraxis_showscale=False,
                    template="plotly_white",
                )
                st.plotly_chart(fig_bar, use_container_width=True, key="chart_gap_bar")

                # 전세가율 추이
                fig_ratio = px.line(
                    gap_df, x="ym", y="전세가율(%)",
                    title="월별 전세가율 (%)",
                    labels={"ym": "년월", "전세가율(%)": "전세가율 (%)"},
                    markers=True,
                )
                fig_ratio.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="70% 과열 기준")
                fig_ratio.update_traces(line_color="#7c3aed", line_width=2)
                fig_ratio.update_layout(xaxis_tickangle=-45, template="plotly_white")
                st.plotly_chart(fig_ratio, use_container_width=True, key="chart_gap_ratio")

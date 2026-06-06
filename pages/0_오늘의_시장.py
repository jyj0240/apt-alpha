"""내 단지 — 단지 중심 홈.

타겟/관심 단지를 추가하면, 그 단지가 '동급 단지(같은 구·비슷한 면적·연식)' 대비
어디쯤인지(순위·평균 대비·고점 대비)를 한 문장으로 평가한다.
시장 전체 상황은 맨 아래 '배경'으로만 보조한다.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from data_pipeline import current_filters, load_trade
from data_processor import (
    calc_apt_peak_drop,
    aggregate_by_gu_month,
    calc_period_change,
    calc_recent_momentum,
)
from design_system import (
    verdict_card, signal_from_metrics, hero_metrics, show_chart, create_figure,
    format_price, format_sqm_price, format_pct, COLORS,
)
from sidebar_filters import render_sidebar_filters
from watchlist import load_watchlist, add_to_watchlist, remove_from_watchlist, key_of
from comp_mapping import comparable_dongs, cluster_for, find_comparables_across
from app_defaults import DEFAULT_GUS

render_sidebar_filters()

f = current_filters()
gus = f["gus"] or list(DEFAULT_GUS)

st.markdown("### 내 단지")
st.caption("관심·타겟 단지를 추가하면 동급 단지 대비 위치를 평가합니다. 비교군은 시장 대장군·인접 동을 매핑해 구 경계를 넘습니다.")


def render_complex_card(item: dict):
    """관심 단지 1개의 상대 평가 카드를 렌더한다."""
    gu, dong, apt, area = item["gu"], item["dong"], item["apt"], item["area"]
    k = key_of(item)

    head, btn = st.columns([5, 1])
    head.markdown(f"#### {apt} · {area}㎡  ·  {gu} {dong}")
    if btn.button("삭제", key=f"rm_{k}"):
        remove_from_watchlist(k)
        st.rerun()

    # 비교군 매핑: 구 경계를 넘는 동급/인접 동 풀을 구성
    scope, group_name, mapped = comparable_dongs(gu, dong)
    gus_needed = sorted({g for g, _ in scope})
    frames = [
        load_trade([g], f["start_ym"], f["end_ym"],
                   area=None, build_year=None, exclude_outliers=f["exclude_outliers"])
        for g in gus_needed
    ]
    frames = [x for x in frames if not x.empty]
    if not frames:
        st.caption("비교 지역 데이터가 없습니다.")
        return
    pool = pd.concat(frames, ignore_index=True)
    if mapped:
        keyset = {f"{g}|{d}" for g, d in scope}
        pool = pool[(pool["gu_name"] + "|" + pool["dong"]).isin(keyset)]

    tgt = pool[(pool["gu_name"] == gu) & (pool["dong"] == dong) & (pool["apt_name"] == apt)]
    tgt = tgt[tgt["area"].round(0).astype(int) == area]
    if tgt.empty:
        st.caption("이 면적대의 거래가 없습니다. (기간을 늘려보세요)")
        return

    build_yr = int(tgt["build_year"].median()) if tgt["build_year"].notna().any() else 0
    latest_price = tgt.groupby("ym")["price"].median().sort_index().iloc[-1]
    latest_sqm = float(tgt["price_per_sqm"].median())

    pk = calc_apt_peak_drop(tgt)
    drop = float(pk.iloc[0]["drop_pct"]) if not pk.empty else 0.0

    cl_name, cl_keys = cluster_for(apt)
    comps = find_comparables_across(pool, gu, dong, apt, build_yr, float(area), cluster_keys=cl_keys)

    if not comps.empty and comps["is_target"].any() and len(comps) >= 2:
        cs = comps.sort_values("median_sqm", ascending=False).reset_index(drop=True)
        n = len(cs)
        rank = int(cs.index[cs["is_target"]][0]) + 1
        tsqm = float(cs.loc[cs["is_target"], "median_sqm"].iloc[0])
        others = cs[~cs["is_target"]]
        avg_o = float(others["median_sqm"].mean()) if not others.empty else tsqm
        diff = round((tsqm - avg_o) / avg_o * 100, 1) if avg_o > 0 else 0.0

        if diff <= -5:
            sig = {"label": "동급 대비 저평가", "color": COLORS["primary"]}
        elif diff >= 5:
            sig = {"label": "동급 대비 고평가", "color": COLORS["down"]}
        else:
            sig = {"label": "동급과 비슷", "color": COLORS["neutral"]}

        if cl_name:
            scope_txt = f"비교군: {cl_name}(시장 대장군)"
        elif group_name:
            scope_txt = f"비교 범위: {group_name}(구 경계 포함)"
        else:
            scope_txt = "비교 범위: 같은 구"
        verdict_card(
            f"동급 {n}곳 중 {rank}위 · 평균 대비 {diff:+.1f}%",
            sub=f"고점 대비 {drop:+.1f}%. {scope_txt}. 동급 = 비슷한 면적·연식 단지.",
            signal=sig,
        )
        hero_metrics([
            ("현재가", format_price(latest_price)),
            ("m2당", format_sqm_price(latest_sqm)),
            ("동급 평균 대비", format_pct(diff)),
            ("고점 대비", format_pct(drop)),
        ])

        # 동급 비교 막대 (내 단지 강조, 구 경계 넘으므로 동 표기)
        bar = cs.sort_values("median_sqm").copy()
        bar["lbl"] = bar["apt_name"] + " (" + bar["dong"] + ")"
        colors = ["#1d4ed8" if t else "#cbd5e1" for t in bar["is_target"]]
        fig = create_figure(xaxis_title="m2당가 (만원/m2)", yaxis_title="",
                            height=max(200, len(bar) * 34))
        fig.add_trace(go.Bar(
            x=bar["median_sqm"], y=bar["lbl"], orientation="h",
            marker_color=colors,
            text=[f"{v:,.0f}" for v in bar["median_sqm"]],
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>%{x:,.0f}만원/m2<extra></extra>",
        ))
        # 오른쪽 여백 확보 (outside 라벨 잘림 방지)
        max_val = bar["median_sqm"].max()
        fig.update_xaxes(range=[0, max_val * 1.2])
        show_chart(fig, key=f"cmp_{k}")
    else:
        verdict_card(
            f"{apt} 현재가 {format_price(latest_price)}",
            sub=(f"고점 대비 {drop:+.1f}%. 이 면적대 거래가 희소해(대형 평형 등) 동급 비교가 어렵습니다. "
                 "조회 기간을 넓히면 비교가 가능해질 수 있습니다."),
        )
        hero_metrics([
            ("현재가", format_price(latest_price)),
            ("m2당", format_sqm_price(latest_sqm)),
            ("고점 대비", format_pct(drop)),
        ])


# --- 관심 단지 추가 ---
wl = load_watchlist()
with st.expander("관심 단지 추가", expanded=not wl):
    df_add = load_trade(gus, f["start_ym"], f["end_ym"],
                        area=None, build_year=None, exclude_outliers=f["exclude_outliers"])
    if df_add.empty:
        st.info("관심 지역 데이터가 없습니다. 사이드바에서 지역·기간을 조정하세요.")
    else:
        opts = (
            df_add.groupby(["gu_name", "dong", "apt_name"]).size()
            .reset_index(name="n").sort_values("n", ascending=False)
        )
        opts["label"] = opts["apt_name"] + " [" + opts["gu_name"] + " " + opts["dong"] + "]"
        label_map = {r["label"]: (r["gu_name"], r["dong"], r["apt_name"])
                     for _, r in opts.iterrows()}
        choice = st.selectbox("단지 검색 (관심 지역 내, 타이핑 가능)", [""] + opts["label"].tolist())
        if choice:
            g, d, a = label_map[choice]
            sub = df_add[(df_add["gu_name"] == g) & (df_add["dong"] == d) & (df_add["apt_name"] == a)]
            areas = sub["area"].round(0).astype(int).value_counts().sort_index()
            area_pick = st.selectbox("전용면적", areas.index.tolist(),
                                     format_func=lambda x: f"{x}m2 ({areas[x]}건)")
            if st.button("관심 단지에 추가", type="primary"):
                add_to_watchlist({"gu": g, "dong": d, "apt": a, "area": int(area_pick)})
                st.rerun()

st.divider()

# --- 내 단지 평가 ---
wl = load_watchlist()
if not wl:
    st.info("아직 추가한 단지가 없습니다. 위 '관심 단지 추가'에서 타겟 단지를 골라보세요.")
else:
    for item in wl:
        render_complex_card(item)
        st.divider()

# --- 시장 배경 (보조) ---
df_mkt = load_trade(gus, f["start_ym"], f["end_ym"],
                    area=f["area"], build_year=f["build_year"], exclude_outliers=f["exclude_outliers"])
if not df_mkt.empty:
    agg = aggregate_by_gu_month(df_mkt)
    pg = gus[0]

    def _v(mdf, col):
        r = mdf.loc[mdf["gu_name"] == pg, col]
        return float(r.iloc[0]) if not r.empty else 0.0

    chg = _v(calc_period_change(agg), "change_pct")
    mom = _v(calc_recent_momentum(agg), "momentum_pct")
    sig = signal_from_metrics(change_pct=chg, momentum_pct=mom)
    st.caption(
        f"시장 배경 — {pg} 시장은 '{sig['label']}' (기간 {chg:+.1f}%, 최근 {mom:+.1f}%). "
        f"단지 평가의 비교 기준입니다."
    )

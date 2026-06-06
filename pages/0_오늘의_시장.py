"""🏠 오늘의 시장 — 답 먼저 대시보드 (개편 v1, docs/REDESIGN.md M3).

관심 지역의 현황을 진입 즉시 '한 문장 판정 + 핵심 숫자 + 미니 차트'로 보여준다.
일반 사용자가 3초 안에 "지금 분위기"를 파악하는 것이 목표.
"""

import streamlit as st

from data_pipeline import current_filters, load_trade
from data_processor import (
    aggregate_by_gu_month,
    aggregate_by_apt,
    calc_period_change,
    calc_recent_momentum,
    calc_volatility,
    generate_insight_text,
)
from design_system import (
    verdict_card, signal_from_metrics, hero_metrics, show_chart,
    format_price, format_sqm_price, format_pct,
)
from visualizer import price_trend_chart
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()

f = current_filters()
gus = f["gus"] or ["강남구"]          # 미설정 시 기본 진입 지역
primary_gu = gus[0]

# --- 데이터 ---
df = load_trade(
    gus, f["start_ym"], f["end_ym"],
    area=f["area"], build_year=f["build_year"],
    exclude_outliers=f["exclude_outliers"],
)
if df.empty:
    st.info("선택한 조건의 거래 데이터가 없습니다. 사이드바에서 지역·기간을 바꿔보세요.")
    st.stop()

gu_agg = aggregate_by_gu_month(df)
df_primary = df[df["gu_name"] == primary_gu]
agg_primary = gu_agg[gu_agg["gu_name"] == primary_gu]


def _val(metric_df, col):
    row = metric_df.loc[metric_df["gu_name"] == primary_gu, col]
    return float(row.iloc[0]) if not row.empty else 0.0


change_val = _val(calc_period_change(gu_agg), "change_pct")
momentum_val = _val(calc_recent_momentum(gu_agg), "momentum_pct")
vol_val = _val(calc_volatility(gu_agg), "volatility")

# 최신 평당 시세
latest_sqm = 0.0
if not agg_primary.empty:
    latest_row = agg_primary.sort_values("ym").iloc[-1]
    latest_sqm = float(latest_row["median_price_per_sqm"])

# --- 1층: 판정 카드 ---
period_txt = f"{f['start_ym'][:4]}.{f['start_ym'][4:]}~{f['end_ym'][:4]}.{f['end_ym'][4:]}"
st.markdown(f"### {primary_gu}  ·  {period_txt}")

sig = signal_from_metrics(change_pct=change_val, momentum_pct=momentum_val)
headline = f"지금 {primary_gu}는 '{sig['label']}' 구간입니다."
sub = generate_insight_text(primary_gu, change_val, momentum_val, 0.0, vol_val)
verdict_card(headline, sub=sub, signal=sig)

# --- 2층: 핵심 숫자 ---
hero_metrics([
    ("평당 시세", format_sqm_price(latest_sqm)),
    ("기간 상승률", format_pct(change_val)),
    ("최근 상승세", format_pct(momentum_val)),
    ("거래량", f"{len(df_primary):,}건"),
])

# --- 미니 차트 ---
show_chart(price_trend_chart(gu_agg, gus), key="dash_trend")

st.divider()

# --- 거래가 활발한 단지 Top 3 ---
st.markdown("#### 👉 최근 거래가 활발한 단지")
apt_summary = aggregate_by_apt(df_primary)
if not apt_summary.empty:
    top3 = (
        apt_summary[apt_summary["trade_count"] >= 3]
        .sort_values("trade_count", ascending=False)
        .head(3)
    )
    if top3.empty:
        top3 = apt_summary.sort_values("trade_count", ascending=False).head(3)
    cols = st.columns(len(top3)) if len(top3) > 0 else []
    for col, (_, r) in zip(cols, top3.iterrows()):
        col.metric(
            f"{r['apt_name']}",
            format_price(r["median_price"]),
            delta=f"{r['dong']} · {int(r['trade_count'])}건",
            delta_color="off",
        )
else:
    st.caption("표시할 단지가 없습니다.")

st.divider()

# --- 바로가기 ---
st.markdown('<p style="font-size:0.72rem;font-weight:700;color:#2563eb;'
            'letter-spacing:1px;">자세히 보기</p>', unsafe_allow_html=True)
g1, g2, g3 = st.columns(3)
if g1.button("🗺️ 가격 추이", use_container_width=True):
    st.switch_page("pages/1_가격_추이.py")
if g2.button("🏢 단지 분석", use_container_width=True):
    st.switch_page("pages/5_단지_분석.py")
if g3.button("💰 대출 계산", use_container_width=True):
    st.switch_page("pages/7_대출_시뮬레이터.py")

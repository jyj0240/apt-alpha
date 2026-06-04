import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from design_system import show_chart, COLORS, apply_theme, format_price, format_pct
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()
st.header("LTV / 대출 시뮬레이터")
st.caption("매매가, 대출 조건을 입력하면 월 상환액·이자 총액·실제 투자수익률을 계산합니다.")

st.divider()

# --- 입력 패널 ---
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("매매 조건")
    apt_price = st.number_input("매매가 (만원)", min_value=5000, max_value=500000, value=80000, step=1000)
    jeonse_deposit = st.number_input("전세/임대 보증금 (만원, 없으면 0)", min_value=0, max_value=400000, value=0, step=1000)

    st.subheader("대출 조건")
    ltv_pct = st.slider("LTV (%)", min_value=10, max_value=80, value=40, step=5,
                        help="담보인정비율. 투기과열지구 최대 40%, 조정지역 50%, 비규제 70%.")
    loan_amt_calc = int(apt_price * ltv_pct / 100)
    st.info(f"LTV {ltv_pct}% 적용 시 대출 한도: **{loan_amt_calc:,}만원**")

    loan_amt = st.number_input("실제 대출 금액 (만원)", min_value=0, max_value=loan_amt_calc,
                               value=min(loan_amt_calc, loan_amt_calc), step=500)
    loan_years = st.selectbox("대출 기간 (년)", [10, 15, 20, 25, 30], index=2)
    repay_type = st.selectbox("상환 방식", ["원리금균등", "원금균등", "만기일시"])

with col_right:
    st.subheader("금리 설정")
    rate_mode = st.radio("금리 입력 방식", ["직접 입력", "금리 시나리오 비교"], horizontal=True)

    if rate_mode == "직접 입력":
        annual_rate = st.slider("연이율 (%)", min_value=1.0, max_value=10.0, value=4.0, step=0.1)
        scenario_rates = [annual_rate]
    else:
        st.markdown("시나리오별 연이율 설정")
        r1 = st.number_input("낙관 (금리 인하)", min_value=1.0, max_value=10.0, value=3.0, step=0.1)
        r2 = st.number_input("기준", min_value=1.0, max_value=10.0, value=4.0, step=0.1)
        r3 = st.number_input("비관 (금리 인상)", min_value=1.0, max_value=10.0, value=5.5, step=0.1)
        scenario_rates = [r1, r2, r3]
        annual_rate = r2  # 기준 금리를 기본으로 사용

    st.subheader("수익 분석 (선택)")
    expected_years = st.number_input("예상 보유 기간 (년)", min_value=1, max_value=30, value=5)
    annual_appreciation = st.slider("연간 가격 상승률 가정 (%)", min_value=-5.0, max_value=15.0, value=3.0, step=0.5)
    annual_rent_income = st.number_input("연간 임대 수입 (만원, 없으면 0)", min_value=0, max_value=10000, value=0, step=100)


# --- 계산 함수 ---
def calc_equal_principal_interest(principal_man, annual_rate_pct, years):
    """원리금균등상환: 월 납입액, 총 이자."""
    r = annual_rate_pct / 100 / 12
    n = years * 12
    if r == 0:
        monthly = principal_man / n
        total_interest = 0.0
    else:
        monthly = principal_man * r * (1 + r) ** n / ((1 + r) ** n - 1)
        total_interest = monthly * n - principal_man
    return monthly, total_interest, n


def calc_equal_principal(principal_man, annual_rate_pct, years):
    """원금균등상환: 1회차 납입액, 총 이자."""
    r = annual_rate_pct / 100 / 12
    n = years * 12
    monthly_principal = principal_man / n
    rows = []
    remaining = principal_man
    total_interest = 0.0
    for i in range(1, n + 1):
        interest = remaining * r
        payment = monthly_principal + interest
        rows.append({"회차": i, "납입액": payment, "원금": monthly_principal, "이자": interest, "잔액": remaining - monthly_principal})
        remaining -= monthly_principal
        total_interest += interest
    first_payment = rows[0]["납입액"] if rows else 0
    return first_payment, total_interest, n, pd.DataFrame(rows)


def calc_bullet(principal_man, annual_rate_pct, years):
    """만기일시: 월 이자만 납입, 만기에 원금 상환."""
    r = annual_rate_pct / 100 / 12
    n = years * 12
    monthly = principal_man * r
    total_interest = monthly * n
    return monthly, total_interest, n


# --- 핵심 지표 계산 ---
st.divider()
st.subheader("분석 결과")

equity = apt_price - loan_amt - jeonse_deposit  # 실투자금
if equity <= 0:
    st.error("실투자금(매매가 - 대출 - 전세보증금)이 0 이하입니다. 금액을 확인하세요.")
    st.stop()

# 단일 금리 기준 계산
if repay_type == "원리금균등":
    monthly_payment, total_interest, n_months = calc_equal_principal_interest(loan_amt, annual_rate, loan_years)
elif repay_type == "원금균등":
    monthly_payment, total_interest, n_months, _ = calc_equal_principal(loan_amt, annual_rate, loan_years)
else:  # 만기일시
    monthly_payment, total_interest, n_months = calc_bullet(loan_amt, annual_rate, loan_years)

total_repay = loan_amt + total_interest
dsr_monthly_income = st.number_input("월 소득 (만원, DSR 계산용)", min_value=100, max_value=5000, value=500, step=50)
dsr_pct = (monthly_payment / dsr_monthly_income * 100) if dsr_monthly_income > 0 else 0

# 수익 분석
future_price = apt_price * (1 + annual_appreciation / 100) ** expected_years
total_rent_income = annual_rent_income * expected_years
capital_gain = future_price - apt_price
total_profit = capital_gain + total_rent_income
# 보유 기간 이자 (원리금 기준)
hold_months = int(expected_years * 12)
hold_interest = 0.0
if repay_type == "만기일시":
    hold_interest = monthly_payment * hold_months
elif repay_type == "원리금균등":
    r = annual_rate / 100 / 12
    n = loan_years * 12
    if r > 0:
        for i in range(1, hold_months + 1):
            remaining_principal = loan_amt * ((1 + r) ** n - (1 + r) ** (i - 1)) / ((1 + r) ** n - 1)
            hold_interest += remaining_principal * r
    else:
        hold_interest = 0
else:
    # 원금균등: 이자 합계
    _, _, _, ep_df = calc_equal_principal(loan_amt, annual_rate, loan_years)
    hold_interest = ep_df.head(hold_months)["이자"].sum()

net_profit = total_profit - hold_interest
roi_pct = (net_profit / equity * 100) if equity > 0 else 0
annual_roi = ((1 + roi_pct / 100) ** (1 / expected_years) - 1) * 100 if expected_years > 0 else 0

# --- KPI 표시 ---
kr1 = st.columns(3)
kr1[0].metric("실투자금", f"{equity:,.0f}만원")
kr1[1].metric("월 상환액", f"{monthly_payment:,.0f}만원",
              delta=f"DSR {dsr_pct:.1f}%", delta_color="off")
kr1[2].metric("총 이자", f"{total_interest:,.0f}만원")
kr2 = st.columns(2)
kr2[0].metric(f"{expected_years}년 후 예상가", f"{future_price:,.0f}만원",
              delta=f"+{capital_gain:,.0f}만원", delta_color="normal")
kr2[1].metric("순수익", f"{net_profit:,.0f}만원",
              delta=f"연환산 ROI {annual_roi:.1f}%", delta_color="normal")

st.divider()

# --- 차트 영역 ---
chart_tab1, chart_tab2, chart_tab3 = st.tabs(["상환 스케줄", "금리 시나리오 비교", "레버리지 분석"])

with chart_tab1:
    st.subheader("월별 상환 스케줄")

    if repay_type == "원리금균등":
        r = annual_rate / 100 / 12
        n_t = loan_years * 12
        rows = []
        remaining = loan_amt
        for i in range(1, n_t + 1):
            if r > 0:
                interest_p = remaining * r
                principal_p = monthly_payment - interest_p
            else:
                interest_p = 0
                principal_p = monthly_payment
            remaining -= principal_p
            rows.append({"회차": i, "이자": round(interest_p, 1), "원금": round(principal_p, 1), "잔액": max(0, round(remaining, 1))})
        schedule_df = pd.DataFrame(rows)

    elif repay_type == "원금균등":
        _, _, _, schedule_df = calc_equal_principal(loan_amt, annual_rate, loan_years)
        schedule_df = schedule_df.rename(columns={"납입액": "월납입액"})

    else:  # 만기일시
        n_t = loan_years * 12
        rows = [{"회차": i, "이자": round(monthly_payment, 1), "원금": 0 if i < n_t else loan_amt, "잔액": loan_amt if i < n_t else 0} for i in range(1, n_t + 1)]
        schedule_df = pd.DataFrame(rows)

    # 연간 집계로 시각화
    schedule_df["연도"] = ((schedule_df["회차"] - 1) // 12 + 1)
    annual_schedule = schedule_df.groupby("연도")[["이자", "원금"]].sum().reset_index()

    fig_sched = px.bar(
        annual_schedule.melt(id_vars="연도", value_vars=["원금", "이자"], var_name="구분", value_name="금액"),
        x="연도", y="금액", color="구분",
        color_discrete_map={"원금": "#2563eb", "이자": "#f87171"},
        title="연도별 원금/이자 납입",
        labels={"연도": "경과 연도", "금액": "납입액 (만원)"},
        barmode="stack",
    )
    fig_sched.update_layout(template="plotly_white", hovermode="x unified")
    show_chart(fig_sched, use_container_width=True, key="chart_schedule")

    # 잔액 추이
    annual_balance = schedule_df.groupby("연도")["잔액"].last().reset_index()
    fig_bal = px.area(
        annual_balance, x="연도", y="잔액",
        title="대출 잔액 추이",
        labels={"연도": "경과 연도", "잔액": "잔액 (만원)"},
    )
    fig_bal.update_traces(line_color="#2563eb", fillcolor="rgba(37,99,235,0.15)")
    fig_bal.update_layout(template="plotly_white")
    show_chart(fig_bal, use_container_width=True, key="chart_balance")


with chart_tab2:
    st.subheader("금리 시나리오별 비교")

    if rate_mode == "직접 입력":
        compare_rates = [max(1.0, annual_rate - 1.5), annual_rate, min(10.0, annual_rate + 1.5)]
        labels = [f"낙관 ({compare_rates[0]:.1f}%)", f"기준 ({compare_rates[1]:.1f}%)", f"비관 ({compare_rates[2]:.1f}%)"]
    else:
        compare_rates = scenario_rates
        labels = [f"낙관 ({r:.1f}%)" for r in scenario_rates] if len(scenario_rates) == 1 else \
                 [f"낙관 ({scenario_rates[0]:.1f}%)", f"기준 ({scenario_rates[1]:.1f}%)", f"비관 ({scenario_rates[2]:.1f}%)"]

    scenario_data = []
    for rate, label in zip(compare_rates, labels):
        if repay_type == "원리금균등":
            mp, ti, _ = calc_equal_principal_interest(loan_amt, rate, loan_years)
        elif repay_type == "원금균등":
            mp, ti, _, _ = calc_equal_principal(loan_amt, rate, loan_years)
        else:
            mp, ti, _ = calc_bullet(loan_amt, rate, loan_years)
        scenario_data.append({
            "시나리오": label,
            "월 납입액 (만원)": round(mp, 1),
            "총 이자 (만원)": round(ti, 1),
            "총 상환액 (만원)": round(loan_amt + ti, 1),
            "DSR (%)": round(mp / dsr_monthly_income * 100, 1) if dsr_monthly_income > 0 else 0,
        })

    sc_df = pd.DataFrame(scenario_data)
    st.dataframe(sc_df, use_container_width=True, hide_index=True)

    fig_sc = px.bar(
        sc_df, x="시나리오", y="월 납입액 (만원)",
        color="시나리오",
        color_discrete_sequence=["#16a34a", "#2563eb", "#dc2626"],
        text="월 납입액 (만원)",
        title="금리 시나리오별 월 납입액",
    )
    fig_sc.update_traces(texttemplate="%{text:.0f}만원", textposition="outside")
    fig_sc.update_layout(template="plotly_white", showlegend=False)
    show_chart(fig_sc, use_container_width=True, key="chart_scenario")

    fig_int = px.bar(
        sc_df, x="시나리오", y="총 이자 (만원)",
        color="시나리오",
        color_discrete_sequence=["#16a34a", "#2563eb", "#dc2626"],
        text="총 이자 (만원)",
        title="금리 시나리오별 총 이자 부담",
    )
    fig_int.update_traces(texttemplate="%{text:,.0f}만원", textposition="outside")
    fig_int.update_layout(template="plotly_white", showlegend=False)
    show_chart(fig_int, use_container_width=True, key="chart_total_interest")


with chart_tab3:
    st.subheader("레버리지 효과 분석")
    st.caption("대출 없이 전액 자기자본 투자 vs 현재 대출 조건 비교")

    # 전액 자기자본 투자 수익률
    no_loan_profit = capital_gain + total_rent_income
    no_loan_roi = (no_loan_profit / apt_price * 100) if apt_price > 0 else 0
    no_loan_annual_roi = ((1 + no_loan_roi / 100) ** (1 / expected_years) - 1) * 100 if expected_years > 0 else 0

    lev_data = pd.DataFrame({
        "투자 방식": ["전액 자기자본", f"LTV {ltv_pct}% 대출 활용"],
        "실투자금 (만원)": [apt_price, equity],
        f"{expected_years}년 순수익 (만원)": [round(no_loan_profit, 0), round(net_profit, 0)],
        "연환산 ROI (%)": [round(no_loan_annual_roi, 2), round(annual_roi, 2)],
    })
    st.dataframe(lev_data, use_container_width=True, hide_index=True)

    fig_roi = px.bar(
        lev_data, x="투자 방식", y="연환산 ROI (%)",
        color="투자 방식",
        color_discrete_sequence=["#94a3b8", "#2563eb"],
        text="연환산 ROI (%)",
        title="레버리지 효과: 연환산 ROI 비교",
    )
    fig_roi.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig_roi.update_layout(template="plotly_white", showlegend=False)
    show_chart(fig_roi, use_container_width=True, key="chart_leverage")

    # 가격 상승률별 ROI 민감도
    st.markdown("##### 가격 상승률 변화에 따른 ROI 민감도")
    appr_range = np.arange(-3.0, 12.5, 0.5)
    sensitivity_rows = []
    for appr in appr_range:
        fp = apt_price * (1 + appr / 100) ** expected_years
        cg = fp - apt_price
        np_ = cg + total_rent_income - hold_interest
        roi = (np_ / equity * 100) if equity > 0 else 0
        annual_r = ((1 + roi / 100) ** (1 / expected_years) - 1) * 100 if expected_years > 0 else 0
        sensitivity_rows.append({
            "연간 상승률 (%)": appr,
            "연환산 ROI (%)": round(annual_r, 2),
        })

    sens_df = pd.DataFrame(sensitivity_rows)
    fig_sens = px.line(
        sens_df, x="연간 상승률 (%)", y="연환산 ROI (%)",
        title="가격 상승률 가정별 연환산 ROI",
        markers=True,
    )
    fig_sens.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="손익분기")
    fig_sens.add_vline(x=annual_appreciation, line_dash="dot", line_color="#2563eb",
                       annotation_text=f"현재 가정 {annual_appreciation:.1f}%")
    fig_sens.update_traces(line_color="#7c3aed", line_width=2)
    fig_sens.update_layout(template="plotly_white", hovermode="x unified")
    show_chart(fig_sens, use_container_width=True, key="chart_sensitivity")

import streamlit as st
import pandas as pd
import plotly.express as px

from config import SEOUL_GU_CODES
from data_collector import collect_seoul_data
from data_processor import clean_trade_data
from predictor import AptPricePredictor
from visualizer import sensitivity_chart
from sidebar_filters import render_sidebar_filters

render_sidebar_filters()
st.header("아파트 가격 예측")

start_ym = st.session_state.get("start_ym", "202401")
end_ym = st.session_state.get("end_ym", "202412")


# 학습 데이터 로드
@st.cache_data(show_spinner="학습 데이터 로딩 중...")
def get_training_data(s_ym, e_ym):
    return collect_seoul_data(s_ym, e_ym)


raw_df = get_training_data(start_ym, end_ym)

if raw_df.empty:
    st.warning("학습할 데이터가 없습니다. 먼저 '가격 추이' 또는 '지도' 페이지에서 데이터를 수집하세요.")
    st.stop()

df = clean_trade_data(raw_df)


# 모델 학습
@st.cache_resource(show_spinner="모델 학습 중...")
def train_model(data_hash):
    predictor = AptPricePredictor()
    metrics = predictor.train(df)
    return predictor, metrics


predictor, metrics = train_model(hash(df.to_json()))

if metrics["train_size"] == 0:
    st.warning("학습에 필요한 충분한 데이터가 없습니다. 더 넓은 기간이나 더 많은 구를 선택하세요.")
    st.stop()

# --- 예측 입력 폼 ---
st.subheader("🤖 아파트 가격 예측")

with st.form("prediction_form"):
    col1, col2 = st.columns(2)
    with col1:
        pred_gu = st.selectbox("조회할 구 선택", list(SEOUL_GU_CODES.values()), key="pred_gu")
        pred_area = st.number_input("전용면적 (m2)", min_value=10.0, max_value=300.0, value=84.0, step=1.0)
        pred_floor = st.number_input("층 선택", min_value=1, max_value=70, value=10)
    with col2:
        pred_age = st.number_input("건물나이 (년)", min_value=0, max_value=60, value=10)
        pred_year = st.number_input("거래년도 (예측 기준)", min_value=2024, max_value=2030, value=2026)
        pred_month = st.number_input("거래월 (예측 기준)", min_value=1, max_value=12, value=6)
    
    submit_btn = st.form_submit_button("가격 예측하기", type="primary", use_container_width=True)

if submit_btn:
    result = predictor.predict(
        area=pred_area, floor=pred_floor, building_age=pred_age,
        gu_name=pred_gu, year=pred_year, month=pred_month,
    )

    if result is None:
        st.error("예측에 실패했습니다. 선택한 구의 데이터가 충분하지 않을 수 있습니다.")
    else:
        # --- 시장가 비교 ---
        similar = df[
            (df["gu_name"] == pred_gu)
            & (df["area"].between(pred_area - 10, pred_area + 10))
        ]
        market_price = similar["price"].median() if not similar.empty else None

        st.success(f"### 예상 거래가격: **{result:,.0f}만원** ({result / 10000:.1f}억원)")

        if market_price:
            diff = result - market_price
            diff_pct = diff / market_price * 100
            m1, m2, m3 = st.columns(3)
            m1.metric("모델 예측가", f"{result:,.0f}만원")
            m2.metric("최근 실거래 중앙가", f"{market_price:,.0f}만원")
            m3.metric("차이", f"{diff:+,.0f}만원 ({diff_pct:+.1f}%)")

            if diff_pct > 5:
                st.caption("💡 모델 예측이 시장가보다 높습니다. 상승 여력이 있거나 고평가 지역일 수 있습니다.")
            elif diff_pct < -5:
                st.caption("💡 모델 예측이 시장가보다 낮습니다. 저평가 구간이거나 하락 요인이 반영되었을 수 있습니다.")
            else:
                st.caption("💡 모델 예측과 시장가가 유사합니다. 현재 시장가 수준이 적절히 반영되었습니다.")

        st.divider()

        # --- 시나리오 비교 & 민감도 ---
        lcol, rcol = st.columns([1, 1.5])
        with lcol:
            st.subheader("📍 같은 조건, 다른 구 비교")
            compare_gus = [g for g in SEOUL_GU_CODES.values() if g != pred_gu][:8]
            scenario_data = [{"구": pred_gu, "예측가(만원)": result, "비고": "선택"}]

            for gu in compare_gus:
                pred_val = predictor.predict(
                    area=pred_area, floor=pred_floor, building_age=pred_age,
                    gu_name=gu, year=pred_year, month=pred_month,
                )
                if pred_val:
                    scenario_data.append({"구": gu, "예측가(만원)": pred_val, "비고": ""})

            scenario_df = pd.DataFrame(scenario_data).sort_values("예측가(만원)", ascending=False)
            st.dataframe(scenario_df, use_container_width=True, hide_index=True)

        with rcol:
            st.subheader("📈 변수별 민감도 분석")
            sensitivity_var = st.selectbox(
                "변화시킬 변수 선택", ["전용면적", "층", "건물나이"], key="sens_var"
            )

            base_params = {
                "area": pred_area, "floor": pred_floor, "building_age": pred_age,
                "gu_name": pred_gu, "year": pred_year, "month": pred_month,
            }

            var_map = {
                "전용면적": ("area", list(range(30, 200, 10))),
                "층": ("floor", list(range(1, 40, 2))),
                "건물나이": ("building_age", list(range(0, 45, 3))),
            }

            param_name, vary_range = var_map[sensitivity_var]
            base_val = base_params.get(param_name)
            fig = sensitivity_chart(predictor, base_params, param_name, vary_range, sensitivity_var, base_value=base_val)
            st.plotly_chart(fig, use_container_width=True, key="chart_sensitivity")

st.divider()

# --- 모델 정보 (하단으로 이동) ---
with st.expander("🛠️ 모델 성능 및 Feature 중요도 보기"):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("MAE", f"{metrics['mae']:,.0f}만원")
    col2.metric("R2 Score", f"{metrics['r2']:.4f}")
    col3.metric("학습 데이터", f"{metrics['train_size']:,}건")
    col4.metric("테스트 데이터", f"{metrics['test_size']:,}건")

    st.caption(
        f"MAE {metrics['mae']:,.0f}만원 = 평균적으로 예측값과 실제값의 차이가 약 {metrics['mae']/10000:.1f}억원 수준입니다. "
        f"R2 {metrics['r2']:.2f} = 모델이 가격 변동의 {metrics['r2']*100:.0f}%를 설명합니다."
    )

    importance = predictor.get_feature_importance()
    if not importance.empty:
        fig = px.bar(
            importance,
            x="importance",
            y="feature_kr",
            orientation="h",
            title="모델 예측 영향도 (Feature Importance)",
            labels={"importance": "중요도", "feature_kr": ""},
        )
        st.plotly_chart(fig, use_container_width=True, key="chart_feature_importance")

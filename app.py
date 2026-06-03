import streamlit as st

from config import API_KEY
from sidebar_filters import render_sidebar_filters

st.set_page_config(
    page_title="서울 아파트 가격 분석",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 반응형 CSS ---
st.markdown("""
<style>
/* === 전체 폰트 사이즈 === */
html, body, [data-testid="stAppViewContainer"] {
    font-size: 14px !important;
}
h1 { font-size: 1.5rem !important; }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1.1rem !important; }
p, li, span, label, .stMarkdown { font-size: 0.9rem !important; }

/* === 레이아웃 기본 === */
.block-container {
    max-width: 100% !important;
    padding: 1rem 2rem !important;
}

/* === 사이드바 (min-width 사용 금지) === */
[data-testid="stSidebar"] {
    background: #f8fafc;
    border-right: 1px solid #e2e8f0;
}

/* === KPI 메트릭 카드 === */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    color: #64748b !important;
    font-weight: 600 !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.72rem !important;
}

/* === 탭 === */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #f1f5f9;
    border-radius: 10px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 6px 14px;
    color: #64748b;
    font-weight: 500;
    font-size: 0.82rem;
}
.stTabs [aria-selected="true"] {
    background: #ffffff;
    color: #2563eb !important;
    font-weight: 600;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* === 구분선 === */
hr { border-color: #e2e8f0 !important; margin: 1.5rem 0 !important; }

/* === 데이터프레임 === */
[data-testid="stDataFrame"] {
    width: 100% !important;
    overflow-x: auto;
}

/* === 히어로 / 카드 === */
.hero-section {
    background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
    border-radius: 16px;
    padding: 36px 32px;
    margin-bottom: 20px;
    border: 1px solid #e2e8f0;
}
.hero-section h1 { font-size: 1.6rem !important; margin-bottom: 4px; }
.hero-section p  { color: #64748b; font-size: 0.85rem; margin: 0; }

.feature-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 10px;
}
.feature-card:hover { border-color: #93c5fd; box-shadow: 0 4px 12px rgba(37,99,235,0.08); }
.feature-card h4 { color: #2563eb; margin-bottom: 6px; font-size: 1rem; }
.feature-card p  { color: #475569; font-size: 0.85rem; line-height: 1.5; margin: 0; }
.feature-card .card-number {
    display: inline-block;
    background: #eff6ff; color: #2563eb; font-weight: 700; font-size: 0.72rem;
    padding: 2px 8px; border-radius: 6px; margin-bottom: 6px;
}

/* === 반응형: 태블릿 === */
@media (max-width: 1024px) {
    .block-container { padding: 1rem 1.5rem !important; }
}

/* === 반응형: 모바일 === */
@media (max-width: 640px) {
    .block-container { padding: 0.75rem 1rem !important; }
    [data-testid="stMetricValue"] { font-size: 0.95rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.65rem !important; }
    .hero-section { padding: 16px 12px; }
    .hero-section h1 { font-size: 1.2rem !important; }
    h1 { font-size: 1.2rem !important; }
    h2 { font-size: 1.05rem !important; }
}
</style>
""", unsafe_allow_html=True)

# API 키 확인
if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
    st.warning(
        "API 키가 설정되지 않았습니다.\n\n"
        "1. https://www.data.go.kr/data/15126469/openapi.do 에서 활용신청\n"
        "2. 프로젝트 루트에 `.env` 파일 생성\n"
        "3. `DATA_GO_KR_API_KEY=발급받은키` 입력"
    )
    st.stop()

render_sidebar_filters()

# --- 히어로 ---
st.markdown("""
<div class="hero-section">
    <h1>Seoul Apartment Analytics</h1>
    <p>서울 25개 구 아파트 매매/전월세 실거래가 분석 대시보드</p>
</div>
""", unsafe_allow_html=True)

st.info("사이드바에서 **지역 / 기간 / 면적대**를 설정한 뒤, 왼쪽 메뉴에서 분석 페이지를 선택하세요.")

# --- 페이지 안내 카드 ---
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("""
    <div class="feature-card">
        <span class="card-number">01</span>
        <h4>가격 추이 분석</h4>
        <p>구별 월별 실거래가 / m2당 가격<br>상승률 랭킹, 변동성 히트맵</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div class="feature-card">
        <span class="card-number">04</span>
        <h4>전월세 분석</h4>
        <p>전세가율 추이, 매매 vs 전세 매트릭스<br>보증금 인상률, 계약 유형</p>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="feature-card">
        <span class="card-number">02</span>
        <h4>서울 구별 지도</h4>
        <p>25개 구 Choropleth<br>5개 지표 리치 툴팁</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div class="feature-card">
        <span class="card-number">05</span>
        <h4>아파트 단지 분석</h4>
        <p>구/동/단지 드릴다운<br>매매-전세 갭, 층수 프리미엄</p>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown("""
    <div class="feature-card">
        <span class="card-number">03</span>
        <h4>가격 예측</h4>
        <p>GBM 머신러닝 예측<br>민감도 분석, 시나리오 비교</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div class="feature-card">
        <span class="card-number">06-07</span>
        <h4>단지 랭킹 / LTV</h4>
        <p>상승/하락 Top N, 전고점 낙폭<br>대출 시뮬레이션, 레버리지 ROI</p>
    </div>
    """, unsafe_allow_html=True)

st.divider()

with st.expander("데이터 출처 및 분석 기준"):
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("**데이터**: 국토교통부 실거래가 API / 매매+전월세")
    with e2:
        st.markdown("**기준**: 전용면적(m2), 중위값(Median), 구+월 캐싱")

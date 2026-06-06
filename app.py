import streamlit as st

from config import API_KEY

st.set_page_config(
    page_title="서울 아파트 가격 분석",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
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

/* === 사이드바 === */
[data-testid="stSidebar"] {
    background: #f8fafc;
    border-right: 1px solid #e2e8f0;
}
/* 사이드바 네비게이션 메뉴 강조 */
[data-testid="stSidebarNav"] a {
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    padding: 8px 12px !important;
    border-radius: 8px !important;
    margin: 2px 4px !important;
}
[data-testid="stSidebarNav"] a:hover {
    background: #eff6ff !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: #2563eb !important;
    color: white !important;
    font-weight: 700 !important;
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

/* === 반응형: 모바일 (iPhone 375~430px) === */
@media (max-width: 640px) {
    .block-container { padding: 0.5rem 0.6rem !important; }

    /* KPI 카드: 2열 강제 + 초소형 */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 6px !important;
    }
    [data-testid="stColumn"] {
        flex: 0 0 48% !important;
        max-width: 48% !important;
    }
    [data-testid="stMetric"] {
        padding: 8px 10px !important;
        border-radius: 8px !important;
    }
    [data-testid="stMetricValue"] { font-size: 0.9rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.7rem !important; }
    [data-testid="stMetricDelta"] { font-size: 0.68rem !important; }

    .stTabs [data-baseweb="tab-list"] { gap: 2px; padding: 2px; }
    .stTabs [data-baseweb="tab"] { padding: 5px 8px; font-size: 0.72rem; }
    h1 { font-size: 1.05rem !important; }
    h3 { font-size: 0.9rem !important; }
    h2 { font-size: 0.88rem !important; }
    h3 { font-size: 0.82rem !important; }
    p, li, span, label, .stMarkdown { font-size: 0.8rem !important; }
    .hero-section { padding: 12px 10px; margin-bottom: 8px; }
    .hero-section h1 { font-size: 1rem !important; }
    .hero-section p { font-size: 0.72rem !important; }
    .feature-card { padding: 10px; margin-bottom: 6px; }
    .feature-card h4 { font-size: 0.82rem; margin-bottom: 4px; }
    .feature-card p { font-size: 0.72rem !important; }
    [data-testid="stDataFrame"] { font-size: 0.72rem; }
    hr { margin: 0.6rem 0 !important; }
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

# --- 네비게이션: 일상 / 전문가용 섹션 분리 ---
# 전문가 모드(사이드바 토글)가 켜져 있을 때만 'Pro' 섹션 페이지를 노출한다.
pro_mode = bool(st.session_state.get("pro_mode", False))

everyday_pages = [
    st.Page("pages/0_오늘의_시장.py", title="오늘의 시장", default=True),
    st.Page("pages/1_가격_추이.py", title="가격 추이"),
    st.Page("pages/4_전월세.py", title="전월세"),
    st.Page("pages/5_단지_분석.py", title="단지 분석"),
    st.Page("pages/6_단지_랭킹.py", title="단지 랭킹"),
    st.Page("pages/11_비교.py", title="비교"),
    st.Page("pages/시작하기.py", title="설정"),
]

pro_pages = [
    st.Page("pages/8_심층_분석.py", title="심층 분석"),
    st.Page("pages/9_알파_분석.py", title="알파·베타"),
    st.Page("pages/10_스크리닝.py", title="스크리닝"),
]

nav_sections = {"일상": everyday_pages}
if pro_mode:
    nav_sections["전문가용"] = pro_pages

pg = st.navigation(nav_sections)
pg.run()

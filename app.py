import streamlit as st

from config import API_KEY
from sidebar_filters import render_sidebar_filters

st.set_page_config(
    page_title="서울 아파트 가격 분석",
    page_icon="",
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

/* === 반응형: 모바일 (iPhone 375~430px) === */
@media (max-width: 640px) {
    .block-container { padding: 0.5rem 0.6rem !important; }
    [data-testid="stMetric"] { padding: 8px 10px !important; }
    [data-testid="stMetricValue"] { font-size: 1rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.62rem !important; }
    [data-testid="stMetricDelta"] { font-size: 0.58rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 2px; padding: 2px; }
    .stTabs [data-baseweb="tab"] { padding: 5px 8px; font-size: 0.68rem; }
    h1 { font-size: 1.05rem !important; }
    h2 { font-size: 0.88rem !important; }
    h3 { font-size: 0.82rem !important; }
    p, li, span, label, .stMarkdown { font-size: 0.78rem !important; }
    .hero-section { padding: 12px 10px; margin-bottom: 8px; }
    .hero-section h1 { font-size: 1rem !important; }
    .hero-section p { font-size: 0.72rem !important; }
    .feature-card { padding: 10px; margin-bottom: 6px; }
    .feature-card h4 { font-size: 0.82rem; margin-bottom: 4px; }
    .feature-card p { font-size: 0.7rem !important; }
    [data-testid="stDataFrame"] { font-size: 0.7rem; }
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

# --- 온보딩: 조건 설정 먼저 ---
st.markdown("""
<div class="hero-section">
    <h1>APT Alpha</h1>
    <p>서울 아파트 실거래가 분석</p>
</div>
""", unsafe_allow_html=True)

from datetime import datetime, timedelta
from config import SEOUL_GU_CODES, AREA_CATEGORIES

st.markdown("### 분석 조건 설정")
st.caption("아래에서 조건을 설정하면 모든 분석 페이지에 자동 적용됩니다.")

# 1. 관심 구 선택
gu_names = list(SEOUL_GU_CODES.values())
selected_gus = st.multiselect(
    "관심 지역",
    gu_names,
    default=st.session_state.get("selected_gus", ["강남구", "서초구"]),
    key="home_gus",
)

# 2. 기간 설정
today = datetime.today()
last_month = today.replace(day=1) - timedelta(days=1)
cur_year = today.year
year_range = list(range(2020, cur_year + 1))
month_range = list(range(1, 13))

def _parse_ym(ym_str, fy, fm):
    try:
        return int(ym_str[:4]), int(ym_str[4:6])
    except (ValueError, IndexError):
        return fy, fm

default_start = f"{last_month.year - 1}{last_month.month:02d}"
default_end = last_month.strftime("%Y%m")
def_sy, def_sm = _parse_ym(st.session_state.get("start_ym", default_start), cur_year - 1, 1)
def_ey, def_em = _parse_ym(st.session_state.get("end_ym", default_end), cur_year, today.month)

st.caption("분석 기간")
pc1, pc2, pc3, pc4 = st.columns(4)
start_year = pc1.selectbox("시작년", year_range,
    index=year_range.index(def_sy) if def_sy in year_range else 0,
    key="home_sy", label_visibility="collapsed", format_func=lambda y: f"{y}년")
start_month = pc2.selectbox("시작월", month_range,
    index=month_range.index(def_sm) if def_sm in month_range else 0,
    key="home_sm", label_visibility="collapsed", format_func=lambda m: f"{m}월")
end_year = pc3.selectbox("종료년", year_range,
    index=year_range.index(def_ey) if def_ey in year_range else len(year_range) - 1,
    key="home_ey", label_visibility="collapsed", format_func=lambda y: f"{y}년")
end_month = pc4.selectbox("종료월", month_range,
    index=month_range.index(def_em) if def_em in month_range else 0,
    key="home_em", label_visibility="collapsed", format_func=lambda m: f"{m}월")

start_ym = f"{start_year}{start_month:02d}"
end_ym = f"{end_year}{end_month:02d}"
if start_ym > end_ym:
    st.warning("시작이 종료보다 늦습니다.")

# 3. 면적대 + 연식
fc1, fc2 = st.columns(2)
area_options = ["전체"] + list(AREA_CATEGORIES.keys())
selected_area = fc1.selectbox("면적대", area_options,
    index=area_options.index(st.session_state.get("selected_area", "전체"))
    if st.session_state.get("selected_area", "전체") in area_options else 0,
    key="home_area")

from sidebar_filters import _build_year_options
build_year_options = _build_year_options()
selected_build_year = fc2.selectbox("연식", build_year_options,
    index=build_year_options.index(st.session_state.get("selected_build_year", "전체"))
    if st.session_state.get("selected_build_year", "전체") in build_year_options else 0,
    key="home_build")

# session_state 업데이트 (사이드바에 자동 반영)
st.session_state["selected_gus"] = selected_gus
st.session_state["start_ym"] = start_ym
st.session_state["end_ym"] = end_ym
st.session_state["selected_area"] = selected_area
st.session_state["selected_build_year"] = selected_build_year

# 사이드바도 렌더 (다른 페이지와 동기화)
render_sidebar_filters()

st.divider()

# 4. 안내
if not selected_gus:
    st.info("위에서 관심 지역을 선택하세요.")
else:
    gu_text = ", ".join(selected_gus)
    st.success(f"**{gu_text}** / {start_year}.{start_month}~{end_year}.{end_month} / {selected_area} / {selected_build_year}")
    st.markdown("왼쪽 메뉴에서 분석 페이지를 선택하세요.")

    # 간단 안내 카드
    st.markdown("### 분석 메뉴")
    m1, m2 = st.columns(2)
    with m1:
        st.markdown("""
        - **가격 추이** — 구별 시세 흐름
        - **구별 지도** — 25개 구 비교
        - **가격 예측** — ML 기반 예측
        - **전월세** — 전세가율 분석
        - **단지 분석** — 개별 단지 상세
        """)
    with m2:
        st.markdown("""
        - **단지 랭킹** — 상승/하락 Top N
        - **대출 시뮬레이터** — LTV/ROI
        - **심층 분석** — STL/리스크/비교
        - **알파 분석** — 팩터 분해
        - **스크리닝** — 퀀트 스코어링
        - **비교** — 단지간 추이 비교
        """)

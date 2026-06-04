import streamlit as st

from config import API_KEY
from sidebar_filters import render_sidebar_filters  # noqa: used in other pages

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

# --- 온보딩 CSS ---
st.markdown("""
<style>
.onboard-title {
    text-align: center;
    padding: 20px 0 8px 0;
}
.onboard-title h1 {
    font-size: 1.8rem !important;
    font-weight: 800 !important;
    color: #2563eb !important;
    margin-bottom: 2px;
}
.onboard-title p {
    color: #64748b;
    font-size: 0.85rem;
}
.step-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #2563eb;
    letter-spacing: 1px;
    margin-bottom: 6px;
    text-transform: uppercase;
}
.summary-box {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0;
    text-align: center;
}
.summary-box .val {
    font-size: 1rem;
    font-weight: 700;
    color: #1e293b;
}
.summary-box .label {
    font-size: 0.7rem;
    color: #64748b;
}

@media (max-width: 640px) {
    .onboard-title h1 { font-size: 1.4rem !important; }
    .onboard-title p { font-size: 0.75rem; }
}
</style>
""", unsafe_allow_html=True)

# --- 온보딩 화면 ---
st.markdown("""
<div class="onboard-title">
    <h1>APT Alpha</h1>
    <p>서울 아파트 실거래가 분석</p>
</div>
""", unsafe_allow_html=True)

from datetime import datetime, timedelta
from config import SEOUL_GU_CODES, AREA_CATEGORIES

# ===== STEP 1: 관심 지역 =====
st.markdown('<p class="step-label">Step 1 &mdash; 관심 지역</p>', unsafe_allow_html=True)

gu_names = list(SEOUL_GU_CODES.values())
gu_short = {g: g.replace("구", "") for g in gu_names}

selected_gus = st.pills(
    "관심 지역",
    gu_names,
    default=st.session_state.get("selected_gus", ["강남구", "서초구"]),
    selection_mode="multi",
    format_func=lambda g: gu_short.get(g, g),
    key="home_gus",
    label_visibility="collapsed",
)
st.session_state["selected_gus"] = list(selected_gus) if selected_gus else []

st.divider()

# ===== STEP 2: 기간 =====
st.markdown('<p class="step-label">Step 2 &mdash; 분석 기간</p>', unsafe_allow_html=True)

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

# 빠른 기간 선택
period_labels = ["1년", "3년", "5년", "전체"]
period_map = {"1년": 1, "3년": 3, "5년": 5, "전체": 0}

# 현재 기간으로 기본값 추정
current_start = st.session_state.get("start_ym", default_start)
diff_months = (int(default_end[:4]) - int(current_start[:4])) * 12 + int(default_end[4:]) - int(current_start[4:])
if diff_months <= 14:
    default_period = "1년"
elif diff_months <= 38:
    default_period = "3년"
elif diff_months <= 62:
    default_period = "5년"
else:
    default_period = "전체"

selected_period = st.pills(
    "기간",
    period_labels,
    default=default_period,
    key="home_period",
    label_visibility="collapsed",
)

if selected_period:
    years_back = period_map.get(selected_period, 1)
    if years_back == 0:
        st.session_state["start_ym"] = "202001"
    else:
        sy = last_month.year - years_back
        sm = last_month.month
        st.session_state["start_ym"] = f"{sy}{sm:02d}"
    st.session_state["end_ym"] = default_end

# 세부 조정
with st.expander("기간 직접 설정"):
    pc1, pc2 = st.columns(2)
    start_year = pc1.selectbox("시작", year_range,
        index=year_range.index(def_sy) if def_sy in year_range else 0,
        key="home_sy", format_func=lambda y: f"{y}년")
    start_month = pc2.selectbox("월", month_range,
        index=month_range.index(def_sm) if def_sm in month_range else 0,
        key="home_sm", format_func=lambda m: f"{m}월")
    ec1, ec2 = st.columns(2)
    end_year = ec1.selectbox("종료", year_range,
        index=year_range.index(def_ey) if def_ey in year_range else len(year_range) - 1,
        key="home_ey", format_func=lambda y: f"{y}년")
    end_month = ec2.selectbox("월 ", month_range,
        index=month_range.index(def_em) if def_em in month_range else 0,
        key="home_em", format_func=lambda m: f"{m}월")
    st.session_state["start_ym"] = f"{start_year}{start_month:02d}"
    st.session_state["end_ym"] = f"{end_year}{end_month:02d}"

start_ym = st.session_state.get("start_ym", default_start)
end_ym = st.session_state.get("end_ym", default_end)

st.divider()

# ===== STEP 3: 면적대 =====
st.markdown('<p class="step-label">Step 3 &mdash; 면적대</p>', unsafe_allow_html=True)

area_all_options = ["전체"] + list(AREA_CATEGORIES.keys())
area_short = {
    "전체": "전체",
    "~60m2 소형": "소형",
    "60~85m2 국민": "국민평형",
    "85~102m2 중형": "중형",
    "102~135m2 중대형": "중대형",
    "135m2~ 대형": "대형",
}

selected_area = st.pills(
    "면적대",
    area_all_options,
    default=st.session_state.get("selected_area", "전체"),
    format_func=lambda a: area_short.get(a, a),
    key="home_area",
    label_visibility="collapsed",
)
st.session_state["selected_area"] = selected_area if selected_area else "전체"

st.divider()

# ===== STEP 4: 연식 =====
st.markdown('<p class="step-label">Step 4 &mdash; 연식</p>', unsafe_allow_html=True)

from sidebar_filters import _build_year_options
build_year_options = _build_year_options()
build_short = {opt: opt.split(" ")[0] for opt in build_year_options}

selected_build_year = st.pills(
    "연식",
    build_year_options,
    default=st.session_state.get("selected_build_year", "전체"),
    format_func=lambda b: build_short.get(b, b),
    key="home_build",
    label_visibility="collapsed",
)
st.session_state["selected_build_year"] = selected_build_year if selected_build_year else "전체"

st.divider()

# ===== 설정 요약 =====
selected_gus = st.session_state.get("selected_gus", [])
selected_area = st.session_state.get("selected_area", "전체")
selected_build_year = st.session_state.get("selected_build_year", "전체")

# 홈에서는 사이드바를 렌더하지 않음 (key 충돌 방지)
# 다른 페이지에서 render_sidebar_filters()가 session_state를 읽어감

if not selected_gus:
    st.info("Step 1에서 관심 지역을 선택하세요.")
else:
    s_ym = st.session_state.get("start_ym", default_start)
    e_ym = st.session_state.get("end_ym", default_end)
    gu_text = " / ".join(selected_gus)
    period_text = f"{s_ym[:4]}.{s_ym[4:]}~{e_ym[:4]}.{e_ym[4:]}"

    st.markdown(f"""
    <div class="summary-box">
        <div class="val">{gu_text}</div>
        <div class="label">{period_text} / {selected_area} / {selected_build_year}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # 바로가기 버튼 (큰 터치 타겟)
    st.markdown('<p class="step-label">분석 시작</p>', unsafe_allow_html=True)

    go1, go2 = st.columns(2)
    if go1.button("가격 추이", key="go_trend", use_container_width=True, type="primary"):
        st.switch_page("pages/1_가격_추이.py")
    if go2.button("구별 지도", key="go_map", use_container_width=True):
        st.switch_page("pages/2_구별_지도.py")

    go3, go4 = st.columns(2)
    if go3.button("단지 분석", key="go_apt", use_container_width=True):
        st.switch_page("pages/5_단지_분석.py")
    if go4.button("비교", key="go_compare", use_container_width=True):
        st.switch_page("pages/11_비교.py")

    go5, go6 = st.columns(2)
    if go5.button("스크리닝", key="go_screen", use_container_width=True):
        st.switch_page("pages/10_스크리닝.py")
    if go6.button("알파 분석", key="go_alpha", use_container_width=True):
        st.switch_page("pages/9_알파_분석.py")

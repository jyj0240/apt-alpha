"""시작하기 — 관심 지역·기간·면적·연식을 한 번에 설정하는 온보딩 화면.

(기존 app.py 홈에 있던 4-step 온보딩을 st.navigation 도입에 맞춰 독립 페이지로 분리.)
사이드바 필터로도 같은 값을 바꿀 수 있으며, 여기서 설정한 값은 session_state로 공유된다.
"""

import streamlit as st
from datetime import datetime, timedelta

from config import SEOUL_GU_CODES, AREA_CATEGORIES, DEFAULT_GUS, DEFAULT_AREA, DEFAULT_START_YM
from sidebar_filters import _build_year_options

st.markdown("""
<style>
.onboard-title { text-align: center; padding: 12px 0 8px 0; }
.onboard-title h1 { font-size: 1.6rem !important; font-weight: 800 !important;
    color: #2563eb !important; margin-bottom: 2px; }
.onboard-title p { color: #64748b; font-size: 0.85rem; }
.step-label { font-size: 0.72rem; font-weight: 700; color: #2563eb;
    letter-spacing: 1px; margin-bottom: 6px; text-transform: uppercase; }
.summary-box { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px;
    padding: 16px; margin: 8px 0; text-align: center; }
.summary-box .val { font-size: 1rem; font-weight: 700; color: #1e293b; }
.summary-box .label { font-size: 0.72rem; color: #64748b; }
@media (max-width: 640px) {
    .onboard-title h1 { font-size: 1.4rem !important; }
    .onboard-title p { font-size: 0.78rem; }
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="onboard-title">
    <h1>APT Alpha</h1>
    <p>관심 지역과 기간을 설정하세요</p>
</div>
""", unsafe_allow_html=True)

# ===== STEP 1: 관심 지역 =====
st.markdown('<p class="step-label">Step 1 &mdash; 관심 지역</p>', unsafe_allow_html=True)

gu_names = list(SEOUL_GU_CODES.values())
gu_short = {g: g.replace("구", "") for g in gu_names}

selected_gus = st.pills(
    "관심 지역", gu_names,
    default=st.session_state.get("selected_gus", list(DEFAULT_GUS)),
    selection_mode="multi",
    format_func=lambda g: gu_short.get(g, g),
    key="home_gus", label_visibility="collapsed",
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


default_start = DEFAULT_START_YM
default_end = last_month.strftime("%Y%m")
def_sy, def_sm = _parse_ym(st.session_state.get("start_ym", default_start), cur_year - 1, 1)
def_ey, def_em = _parse_ym(st.session_state.get("end_ym", default_end), cur_year, today.month)

period_labels = ["1년", "3년", "5년", "전체"]
period_map = {"1년": 1, "3년": 3, "5년": 5, "전체": 0}

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
    "기간", period_labels, default=default_period,
    key="home_period", label_visibility="collapsed",
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

st.divider()

# ===== STEP 3: 면적대 =====
st.markdown('<p class="step-label">Step 3 &mdash; 면적대</p>', unsafe_allow_html=True)

area_all_options = ["전체"] + list(AREA_CATEGORIES.keys())
area_short = {
    "전체": "전체", "~60m2 소형": "소형", "60~85m2 국민": "국민평형",
    "85~102m2 중형": "중형", "102~135m2 중대형": "중대형", "135m2~ 대형": "대형",
}

selected_area = st.pills(
    "면적대", area_all_options,
    default=st.session_state.get("selected_area", DEFAULT_AREA),
    format_func=lambda a: area_short.get(a, a),
    key="home_area", label_visibility="collapsed",
)
st.session_state["selected_area"] = selected_area if selected_area else "전체"

st.divider()

# ===== STEP 4: 연식 =====
st.markdown('<p class="step-label">Step 4 &mdash; 연식</p>', unsafe_allow_html=True)

build_year_options = _build_year_options()
build_short = {opt: opt.split(" ")[0] for opt in build_year_options}

selected_build_year = st.pills(
    "연식", build_year_options,
    default=st.session_state.get("selected_build_year", "전체"),
    format_func=lambda b: build_short.get(b, b),
    key="home_build", label_visibility="collapsed",
)
st.session_state["selected_build_year"] = selected_build_year if selected_build_year else "전체"

st.divider()

# ===== 설정 요약 + 바로가기 =====
selected_gus = st.session_state.get("selected_gus", [])
selected_area = st.session_state.get("selected_area", "전체")
selected_build_year = st.session_state.get("selected_build_year", "전체")

if not selected_gus:
    st.info("Step 1에서 관심 지역을 선택하세요.")
else:
    s_ym = st.session_state.get("start_ym", default_start)
    e_ym = st.session_state.get("end_ym", default_end)
    gu_text = " / ".join(selected_gus)
    period_text = f"{s_ym[:4]}.{s_ym[4:]}~{e_ym[:4]}.{e_ym[4:]}"

    st.markdown(
        f'<div class="summary-box"><div class="val">{gu_text}</div>'
        f'<div class="label">{period_text} / {selected_area} / {selected_build_year}</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<p class="step-label">분석 시작</p>', unsafe_allow_html=True)

    go1, go2 = st.columns(2)
    if go1.button("내 단지", key="go_today", use_container_width=True, type="primary"):
        st.switch_page("pages/0_오늘의_시장.py")
    if go2.button("가격 추이", key="go_trend", use_container_width=True):
        st.switch_page("pages/1_가격_추이.py")

    go3, go4 = st.columns(2)
    if go3.button("단지 분석", key="go_apt", use_container_width=True):
        st.switch_page("pages/5_단지_분석.py")
    if go4.button("전월세", key="go_rent", use_container_width=True):
        st.switch_page("pages/4_전월세.py")

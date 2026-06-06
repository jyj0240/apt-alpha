import streamlit as st

# 배포 후 stale 모듈 캐시로 인한 ImportError 방지 — 프로젝트 import보다 먼저 실행.
import _startup_reload
_startup_reload.refresh()

from config import API_KEY

st.set_page_config(
    page_title="서울 아파트 가격 분석",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Pretendard 폰트 CDN ---
st.markdown(
    '<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>'
    '<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9'
    '/dist/web/variable/pretendardvariable-dynamic-subset.min.css" rel="stylesheet">',
    unsafe_allow_html=True,
)

# --- 반응형 CSS (Design System v2) ---
# NOTE: st.markdown의 HTML 파서가 <style> 안의 > 와 < 를 태그로 오인하므로,
#       CSS 파일을 읽어 f-string으로 주입한다.
import pathlib as _pathlib
_css_text = (_pathlib.Path(__file__).parent / "style.css").read_text(encoding="utf-8")
st.markdown(f"<style>{_css_text}</style>", unsafe_allow_html=True)

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
    st.Page("pages/0_오늘의_시장.py", title="내 단지", default=True),
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

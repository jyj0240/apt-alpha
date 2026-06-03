import os
from dotenv import load_dotenv

load_dotenv()

# API 키: .env (로컬) 또는 Streamlit Secrets (클라우드) 에서 읽기
API_KEY = os.getenv("DATA_GO_KR_API_KEY", "")
if not API_KEY:
    try:
        import streamlit as st
        API_KEY = st.secrets.get("DATA_GO_KR_API_KEY", "")
    except Exception:
        pass

# 국토교통부 아파트매매 실거래자료 API
APT_TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"

# 국토교통부 아파트 전월세 실거래자료 API
APT_RENT_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

# 서울 25개 구 법정동 코드 (앞 5자리)
SEOUL_GU_CODES = {
    "11110": "종로구",
    "11140": "중구",
    "11170": "용산구",
    "11200": "성동구",
    "11215": "광진구",
    "11230": "동대문구",
    "11260": "중랑구",
    "11290": "성북구",
    "11305": "강북구",
    "11320": "도봉구",
    "11350": "노원구",
    "11380": "은평구",
    "11410": "서대문구",
    "11440": "마포구",
    "11470": "양천구",
    "11500": "강서구",
    "11530": "구로구",
    "11545": "금천구",
    "11560": "영등포구",
    "11590": "동작구",
    "11620": "관악구",
    "11650": "서초구",
    "11680": "강남구",
    "11710": "송파구",
    "11740": "강동구",
}

# 코드 -> 구명, 구명 -> 코드 양방향 매핑
GU_CODE_TO_NAME = SEOUL_GU_CODES
GU_NAME_TO_CODE = {v: k for k, v in SEOUL_GU_CODES.items()}

# 면적대 분류 기준 (전용면적 m2 기준)
AREA_CATEGORIES = {
    "~60m2 소형":       (0,   60),
    "60~85m2 국민":     (60,  85),
    "85~102m2 중형":    (85,  102),
    "102~135m2 중대형": (102, 135),
    "135m2~ 대형":      (135, 9999),
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

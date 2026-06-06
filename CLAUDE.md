# APT Alpha — 서울 아파트 실거래가 분석 플랫폼

## 프로젝트 개요

서울 25개 구 아파트 매매/전월세 실거래가를 수집·분석·시각화하는 Streamlit 멀티페이지 웹앱.
국토교통부 공공데이터 API 기반. 단순 가격 조회를 넘어 **퀀트 투자 분석 도구**(팩터 모델,
스크리닝, 가격 예측, 대출 시뮬레이션)를 지향한다.

## 기술 스택

- Python 3.10+ (PEP 604 `X | None` 문법 사용)
- Streamlit (멀티페이지 앱, `st.pills` 기반 필터 UI)
- pandas, plotly, folium, streamlit-folium
- scikit-learn (GradientBoosting 가격 예측)
- statsmodels (알파/베타 OLS 회귀)
- python-dotenv (API 키 관리)

## 실행 방법

```bash
pip install -r requirements.txt
# .env 파일에 API 키 설정 (.env.example 참고)
streamlit run app.py
```

## 프로젝트 구조

```
app.py                  # 진입점 — 온보딩 홈(4-step 필터 설정) + 전역 반응형 CSS
config.py               # API 키, URL, 서울 25개 구 코드, 면적대 분류, DATA_DIR
collect_data.py         # CLI 일괄 수집 스크립트 (캐시 워밍업용)

# --- 데이터 계층 ---
data_collector.py       # 국토부 API 호출 + 구·월 단위 CSV 캐싱 (TTL 차등)
data_processor.py       # 정제/집계 + 30여 개 파생지표 (모멘텀/변동성/MDD/유동성/투자점수)

# --- 분석 계층 ---
factor_model.py         # 알파/베타 5팩터 회귀 모델 (statsmodels OLS, 롤링 윈도우)
screener.py             # 퍼센타일 기반 단지 스크리닝/다차원 스코어링
predictor.py            # GradientBoosting 가격 예측 (AptPricePredictor 클래스)

# --- 표현 계층 ---
visualizer.py           # plotly 차트 함수들
design_system.py        # 공통 테마(COLORS/CHART_LAYOUT), 포맷터, hover 템플릿, show_chart
map_view.py             # 구별 choropleth 지도
sidebar_filters.py      # 페이지 공통 사이드바 필터 (render_sidebar_filters)

pages/
  1_가격_추이.py          # 구/동별 중위가·평당가·거래량 시계열 + KPI
  2_구별_지도.py          # Plotly choropleth (지표 토글)
  3_가격_예측.py          # ML 예측 + 시나리오/민감도
  4_전월세.py            # 전세가율, 계약유형 비중, 갱신(escalation) 분석
  5_단지_분석.py          # 개별 단지 가격 이력 + 고점 대비 하락
  6_단지_랭킹.py          # 단지별 정렬/랭킹
  7_대출_시뮬레이터.py     # DSR/원리금 시뮬레이션
  8_심층_분석.py          # 시계열 분해, 롤링 변동성, MDD
  9_알파_분석.py          # 5팩터로 단지 수익률을 시장β와 고유α로 분해
  10_스크리닝.py          # 조건 필터링 + 투자 스코어 랭킹
  11_비교.py             # 단지/구 다중 비교

data/
  seoul_gu_codes.json   # 25개 구 법정동 코드
  seoul_geo.json        # 서울 구 경계 GeoJSON
  cache_meta.json       # 캐시 TTL 관리용 메타데이터 (cache_key → last_fetched)
  trade_{구코드}_{YYYYMM}.csv   # 매매 캐시 (구+월 단위)
  rent_{구코드}_{YYYYMM}.csv    # 전월세 캐시 (구+월 단위)
```

## 핵심 규칙

### API 키
- `.env`(로컬) 또는 Streamlit Secrets(클라우드)에서 읽음. config.py가 양쪽 처리.
- Encoding 키(`%2B` 형태) 저장 시 data_collector.py가 `%` 포함 여부로 자동 감지하여
  urlencode 우회.

### 캐싱 전략 (data_collector.py)
- `data/{trade,rent}_{구코드}_{YYYYMM}.csv` 구·월 단위 개별 캐싱.
- **TTL 차등** (cache_meta.json 기반):
  - 2개월+ 전(확정) → 영구 캐시
  - 1~2개월 전(준확정) → 7일 TTL (신고 지연분 반영)
  - 당월(미확정) → 1일 TTL (계속 추가됨)
- 빈 결과도 빈 CSV로 기록해 불필요한 재호출 방지. `force_refresh=True`로 전체 무시 가능.
- API 호출 간 `time.sleep(0.3)` 레이트 리밋.

### 세션 상태 (페이지 간 공유)
홈(app.py)에서 4-step으로 설정 → 전 페이지가 session_state로 공유:
`selected_gus`, `start_ym`, `end_ym`, `selected_area`, `selected_build_year`.
다른 페이지는 `render_sidebar_filters()`로 동일 필터를 사이드바에 렌더.

### 데이터 파이프라인 관례
- 수집 직후 항상 `clean_trade_data()` / `clean_rent_data()`로 정제(타입 변환, 평당가 계산 등).
- 면적/연식 필터는 `add_area_category()` 후 `filter_by_area()` / `filter_by_build_year()`.
- 팩터·변동성 계산은 면적 혼합 효과 제거를 위해 **평당가(price_per_sqm) 기준** 사용.

### UI/스타일
- 차트는 `design_system.show_chart()`로 렌더 (모바일 줌/드래그 비활성 config 포함).
- 색상/레이아웃/숫자 포맷은 design_system.py의 공통 함수 사용 (직접 하드코딩 지양).
- app.py에 모바일 반응형 CSS 집중 (≤640px에서 KPI 2열 강제 등).
- **이모지는 절제한다(금융·데이터 앱은 절제된 톤이 신뢰감을 준다).**
  - 헤더·버튼·캡션·본문·네비게이션 메뉴에 **장식용 이모지 금지**.
  - 상태/의미 표시는 이모지 대신 **색 + 텍스트**로 (예: 신호등은 색 pill + "과열/보합/조정" 글자).
  - 예외는 브라우저 탭 favicon(`page_icon`) 정도. 새 코드에 이모지를 넣지 말 것.

## 분석 모델 개념

### 팩터 모델 (factor_model.py)
```
R_단지(t) = α + β₁·R_서울 + β₂·R_구 + β₃·R_면적대 + β₄·R_연식 + β₅·Δ전세가율 + ε
```
- 각 팩터는 **직교화**(해당 구 제외, 상위 벤치마크 차감)하여 중복 제거.
- 롤링 OLS로 시변 α/β 추출, 수익률을 팩터별 기여분으로 분해(`decompose_returns`).
- 전세가율 팩터는 `inject_jeonse_factor()`로 외부 주입.

### 스크리닝 (screener.py)
- 주식 퀀트 팩터 스크리닝과 동일 개념. 단지를 다차원(모멘텀/밸류/유동성 등)
  퍼센타일 스코어링 후 랭킹.

## 데이터 소스

| 데이터 | API endpoint |
|---|---|
| 아파트 매매 실거래가 | apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade |
| 아파트 전월세 실거래가 | apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent |

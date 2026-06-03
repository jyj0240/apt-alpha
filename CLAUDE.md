# 서울 아파트 가격 분석 프로젝트

## 프로젝트 개요

서울 25개 구 아파트 매매/전월세 실거래가를 수집, 분석, 시각화하는 Streamlit 웹앱.
국토교통부 공공데이터 API 기반.

## 기술 스택

- Python 3.10+
- Streamlit (멀티페이지 앱)
- pandas, plotly, folium, streamlit-folium
- scikit-learn (GradientBoosting 가격 예측)
- python-dotenv (API 키 관리)

## 실행 방법

```bash
pip install -r requirements.txt
# .env 파일에 API 키 설정 (.env.example 참고)
streamlit run app.py
```

## 프로젝트 구조

```
app.py                  # Streamlit 메인 (사이드바 공통 필터)
config.py               # API 키, 상수, 서울 25개 구 법정동 코드
data_collector.py        # 국토부 API 호출 + 구+월 단위 CSV 캐싱
data_processor.py        # 데이터 정제/가공/집계/파생지표
visualizer.py            # plotly 차트 함수들
map_view.py              # folium choropleth 지도
predictor.py             # ML 가격 예측 (GradientBoosting)
pages/
  1_price_trend.py       # 가격 추이 분석
  2_map.py               # 서울 구별 지도
  3_prediction.py        # 가격 예측
  4_rent.py              # 전월세 분석
data/
  seoul_gu_codes.json    # 25개 구 법정동 코드
  seoul_geo.json         # 서울 구 경계 GeoJSON
  trade_*.csv            # 매매 캐시 (구+월 단위)
  rent_*.csv             # 전월세 캐시 (구+월 단위)
```

## 핵심 규칙

- API 키는 .env에 Encoding 키(%2B 형태) 저장. data_collector.py가 자동 감지 처리
- 데이터 캐싱: `data/trade_{구코드}_{YYYYMM}.csv` 형태로 구+월 단위 개별 캐싱. 한번 받은 데이터는 API 재호출 안 함
- session_state로 페이지 간 필터 공유: selected_gus, start_ym, end_ym, selected_area

## 데이터 소스

| 데이터 | API endpoint |
|---|---|
| 아파트 매매 실거래가 | apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade |
| 아파트 전월세 실거래가 | apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent |

## v2 개선 계획

### Phase 1: data_processor.py 파생지표 추가
- calc_period_change: 구별 기간 상승률
- calc_recent_momentum: 최근 3개월 모멘텀
- calc_relative_premium: 서울 평균 대비 프리미엄
- calc_volatility: 월간 변동성
- get_dong_gap_summary: 동별 격차
- generate_insight_text: 자동 인사이트 문장

### Phase 2: visualizer.py 차트 추가
- ranking_bar_chart: 랭킹 바차트
- volatility_heatmap: 변동성 히트맵
- scatter_matrix_chart: 2x2 매트릭스 산점도
- sensitivity_chart: 민감도 라인차트

### Phase 3: 가격 추이 페이지 개편
- 상단 KPI 4개 (거래건수, 상승률, 모멘텀, 프리미엄)
- 상승률 랭킹 탭 추가
- 변동성/동별 격차 테이블
- 자동 인사이트 문장

### Phase 4: 지도 페이지 개편
- 지표 토글 5개로 확장 (+ 상승률, 변동성)
- 요약 테이블에 상승률/변동성/프리미엄 컬럼

### Phase 5: 예측 페이지 개편
- 시장가 비교 (예측 vs 최근 실거래 중앙가)
- 시나리오 비교 (구별 예측가 테이블)
- 민감도 차트 (면적/층/연식 변화별 예측가)

### Phase 6: 전월세 페이지 개편
- KPI 4개 (전세 비중, 평균 전세가율, 변화폭, 면적당 월세)
- 2x2 매트릭스 (매매 상승률 vs 전세가율)
- 구별 랭킹 테이블

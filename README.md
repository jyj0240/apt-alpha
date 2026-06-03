# 서울 아파트 가격 분석

서울 25개 구의 아파트 매매 실거래가를 수집/분석/시각화하는 Streamlit 웹앱.

## 기능

- **가격 추이**: 구/동별 중위 실거래가, 평당가, 거래량 시계열 차트
- **지도**: 서울 구별 choropleth 지도 (평당가, 거래량)
- **가격 예측**: GradientBoosting 기반 아파트 가격 예측

## 설치

```bash
pip install -r requirements.txt
```

## API 키 설정

1. [공공데이터포털](https://www.data.go.kr/data/15126469/openapi.do) 접속
2. 회원가입 후 "국토교통부_아파트매매 실거래자료" 활용신청
3. 발급받은 **일반 인증키(Encoding)** 복사
4. 프로젝트 루트에 `.env` 파일 생성:

```
DATA_GO_KR_API_KEY=발급받은_인증키
```

## 실행

```bash
streamlit run app.py
```

## 데이터 소스

| 데이터 | 출처 |
|---|---|
| 아파트 매매 실거래가 | 국토교통부 (data.go.kr) |
| 서울 구 경계 | 간소화 GeoJSON (내장) |

## 기술 스택

Python, Streamlit, pandas, plotly, folium, scikit-learn

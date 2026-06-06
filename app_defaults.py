"""앱 공통 기본 필터값 (단일 출처).

config.py에 정의된 값을 재노출하되, 배포 환경에서 config가 아직 갱신되지
않아 해당 상수가 없더라도 안전하게 동작하도록 fallback을 둔다. (신규 파일은
배포 동기화가 안정적이라, 기존 모듈 수정 지연으로 인한 ImportError를 피한다.)
"""

try:
    from config import DEFAULT_GUS, DEFAULT_AREA, DEFAULT_START_YM
except ImportError:  # config가 아직 옛 버전인 경우의 안전망
    DEFAULT_GUS = ["강남구", "서초구", "송파구"]   # 강남3구
    DEFAULT_AREA = "60~85m2 국민"                  # 국민평형
    DEFAULT_START_YM = "202001"                    # 2020년 1월부터

__all__ = ["DEFAULT_GUS", "DEFAULT_AREA", "DEFAULT_START_YM"]

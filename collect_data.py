"""데이터 수집 / 캐시 워밍업 스크립트.

GitHub Actions(매일 새벽)에서 인자 없이 실행하면 서울 25개 구 전체를
수집한다. 로컬에서 앱을 빠르게 띄우고 싶을 때는 기본 필터(강남3구)만
미리 받아두면 첫 로딩이 즉시 끝난다.

사용법:
    python collect_data.py            # 서울 25개 구 전체 (자동화 기본)
    python collect_data.py --quick    # 기본 필터(강남3구)만 빠른 워밍업
    python collect_data.py 강남구 송파구  # 지정한 구만

기간은 항상 config.DEFAULT_START_YM(2020-01) ~ 현재월. TTL 기반으로
이미 받아둔 확정월은 건너뛴다.
"""

import os
import sys
from datetime import datetime

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(__file__))

from config import SEOUL_GU_CODES, GU_NAME_TO_CODE, DEFAULT_GUS, DEFAULT_START_YM
from data_collector import collect_seoul_data, collect_seoul_rent_data, get_cache_status


def _resolve_gu_codes(args: list[str]) -> tuple[list[str], str]:
    """CLI 인자 → (수집할 구코드 리스트, 사람이 읽을 범위 설명)."""
    if "--quick" in args:
        names = list(DEFAULT_GUS)
        return [GU_NAME_TO_CODE[n] for n in names if n in GU_NAME_TO_CODE], f"기본 필터 {names}"

    explicit = [a for a in args if not a.startswith("-")]
    if explicit:
        codes, names = [], []
        for n in explicit:
            if n in GU_NAME_TO_CODE:
                codes.append(GU_NAME_TO_CODE[n])
                names.append(n)
            else:
                print(f"  (무시) 알 수 없는 구 이름: {n}")
        if codes:
            return codes, f"지정 {names}"

    return list(SEOUL_GU_CODES.keys()), "서울 25개 구 전체"


def main():
    args = sys.argv[1:]
    today = datetime.today()
    start_ym = DEFAULT_START_YM
    end_ym = f"{today.year}{today.month:02d}"

    gu_codes, scope = _resolve_gu_codes(args)

    print("=== 데이터 수집 시작 ===")
    print(f"범위: {scope} ({len(gu_codes)}개 구)")
    print(f"기간: {start_ym} ~ {end_ym}")
    print(f"시각: {today.isoformat()}")
    print()

    status_before = get_cache_status()
    print(f"수집 전: {status_before['total_files']}개 파일, {status_before['total_size_mb']}MB")
    print(f"갱신 필요: {status_before['stale_count']}개")
    print()

    print("--- 매매 데이터 수집 ---")
    trade_df = collect_seoul_data(start_ym, end_ym, gu_codes)
    print(f"매매: {len(trade_df)}건 로드 완료")

    print("--- 전월세 데이터 수집 ---")
    rent_df = collect_seoul_rent_data(start_ym, end_ym, gu_codes)
    print(f"전월세: {len(rent_df)}건 로드 완료")

    status_after = get_cache_status()
    print()
    print("=== 수집 완료 ===")
    print(f"수집 후: {status_after['total_files']}개 파일, {status_after['total_size_mb']}MB")
    print(f"갱신 필요: {status_after['stale_count']}개")
    new_files = status_after['total_files'] - status_before['total_files']
    if new_files > 0:
        print(f"신규 파일: {new_files}개")


if __name__ == "__main__":
    main()

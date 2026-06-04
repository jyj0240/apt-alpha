"""데이터 수집 스크립트 (GitHub Actions에서 실행).

매일 새벽 자동 실행하여 최신 실거래 데이터를 수집하고 CSV로 저장한다.
TTL 기반으로 갱신이 필요한 데이터만 재수집한다.
"""

import os
import sys
from datetime import datetime, timedelta

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(__file__))

from config import SEOUL_GU_CODES
from data_collector import collect_seoul_data, collect_seoul_rent_data, get_cache_status


def main():
    # 수집 기간: 2020-01 ~ 현재월
    today = datetime.today()
    start_ym = "202001"
    end_ym = f"{today.year}{today.month:02d}"

    gu_codes = list(SEOUL_GU_CODES.keys())

    print(f"=== 데이터 수집 시작 ===")
    print(f"기간: {start_ym} ~ {end_ym}")
    print(f"대상: {len(gu_codes)}개 구")
    print(f"시각: {today.isoformat()}")
    print()

    # 수집 전 상태
    status_before = get_cache_status()
    print(f"수집 전: {status_before['total_files']}개 파일, {status_before['total_size_mb']}MB")
    print(f"갱신 필요: {status_before['stale_count']}개")
    print()

    # 매매 데이터 수집
    print("--- 매매 데이터 수집 ---")
    trade_df = collect_seoul_data(start_ym, end_ym, gu_codes)
    print(f"매매: {len(trade_df)}건 로드 완료")

    # 전월세 데이터 수집
    print("--- 전월세 데이터 수집 ---")
    rent_df = collect_seoul_rent_data(start_ym, end_ym, gu_codes)
    print(f"전월세: {len(rent_df)}건 로드 완료")

    # 수집 후 상태
    status_after = get_cache_status()
    print()
    print(f"=== 수집 완료 ===")
    print(f"수집 후: {status_after['total_files']}개 파일, {status_after['total_size_mb']}MB")
    print(f"갱신 필요: {status_after['stale_count']}개")
    new_files = status_after['total_files'] - status_before['total_files']
    if new_files > 0:
        print(f"신규 파일: {new_files}개")


if __name__ == "__main__":
    main()

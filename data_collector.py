import json
import os
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd

from config import API_KEY, APT_TRADE_URL, APT_RENT_URL, SEOUL_GU_CODES, DATA_DIR

# --- XML 필드 매핑 ---

TRADE_FIELD_MAP = {
    "dealAmount": "price",
    "dealingGbn": "trade_type",
    "buildYear": "build_year",
    "dealYear": "year",
    "dealMonth": "month",
    "dealDay": "day",
    "umdNm": "dong",
    "aptNm": "apt_name",
    "excluUseAr": "area",
    "floor": "floor",
    "jibun": "jibun",
}

RENT_FIELD_MAP = {
    "monthlyRent": "monthly_rent",
    "deposit": "deposit",
    "buildYear": "build_year",
    "dealYear": "year",
    "dealMonth": "month",
    "dealDay": "day",
    "umdNm": "dong",
    "aptNm": "apt_name",
    "excluUseAr": "area",
    "floor": "floor",
    "jibun": "jibun",
    "contractType": "contract_type",
    "contractTerm": "contract_term",
    "preDeposit": "prev_deposit",
    "preMonthlyRent": "prev_monthly_rent",
}

# --- 캐시 TTL 설정 (초 단위) ---
# 확정: 2개월+ 전 → 영구 캐시
# 준확정: 1~2개월 전 → 7일 TTL (신고 지연분 반영)
# 미확정: 당월 → 1일 TTL (계속 추가됨)
TTL_RECENT_DAYS = 1       # 당월 캐시 유효기간 (일)
TTL_SEMI_FINAL_DAYS = 7   # 1~2개월 전 캐시 유효기간 (일)
TTL_FINAL_MONTHS = 2      # 이 개월수 이전은 확정 (영구 캐시)

# 메타데이터 파일
_META_FILE = os.path.join(DATA_DIR, "cache_meta.json")


def _load_meta() -> dict:
    """캐시 메타데이터를 로드한다. {cache_key: last_fetched_iso}"""
    if os.path.exists(_META_FILE):
        try:
            with open(_META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_meta(meta: dict):
    """캐시 메타데이터를 저장한다."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _months_ago(ym: str) -> int:
    """주어진 YYYYMM이 현재로부터 몇 개월 전인지 계산한다."""
    now = datetime.now()
    y, m = int(ym[:4]), int(ym[4:6])
    return (now.year - y) * 12 + (now.month - m)


def _cache_expired(cache_key: str, ym: str, meta: dict) -> bool:
    """캐시가 만료되었는지 판단한다.

    Returns:
        True이면 재수집 필요.
    """
    age_months = _months_ago(ym)

    # 확정 데이터: 영구 캐시
    if age_months >= TTL_FINAL_MONTHS:
        return False

    # 메타에 수집 이력이 없으면 만료 처리
    last_fetched_str = meta.get(cache_key)
    if not last_fetched_str:
        return True

    try:
        last_fetched = datetime.fromisoformat(last_fetched_str)
    except (ValueError, TypeError):
        return True

    elapsed_days = (datetime.now() - last_fetched).total_seconds() / 86400

    # 당월: TTL_RECENT_DAYS
    if age_months == 0:
        return elapsed_days >= TTL_RECENT_DAYS

    # 1~2개월 전: TTL_SEMI_FINAL_DAYS
    return elapsed_days >= TTL_SEMI_FINAL_DAYS


def _build_query(gu_code: str, deal_ym: str) -> str:
    """API 쿼리스트링을 구성한다."""
    if "%" in API_KEY:
        return (
            f"serviceKey={API_KEY}"
            f"&LAWD_CD={gu_code}"
            f"&DEAL_YMD={deal_ym}"
            f"&pageNo=1"
            f"&numOfRows=9999"
        )
    return urllib.parse.urlencode({
        "serviceKey": API_KEY,
        "LAWD_CD": gu_code,
        "DEAL_YMD": deal_ym,
        "pageNo": "1",
        "numOfRows": "9999",
    })


def _call_api(base_url: str, gu_code: str, deal_ym: str, field_map: dict) -> pd.DataFrame:
    """공통 API 호출 + XML 파싱."""
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        return pd.DataFrame()

    url = f"{base_url}?{_build_query(gu_code, deal_ym)}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_text = resp.read().decode("utf-8")
    except Exception as e:
        print(f"API 호출 실패: {e}")
        return pd.DataFrame()

    root = ET.fromstring(xml_text)
    items = root.findall(".//item")
    if not items:
        return pd.DataFrame()

    rows = []
    for item in items:
        row = {"gu_code": gu_code}
        for xml_tag, col_name in field_map.items():
            el = item.find(xml_tag)
            row[col_name] = el.text.strip() if el is not None and el.text else ""
        rows.append(row)

    return pd.DataFrame(rows)


def fetch_apt_trade(gu_code: str, deal_ym: str) -> pd.DataFrame:
    """단일 구/월 아파트 매매 실거래 데이터를 조회한다."""
    return _call_api(APT_TRADE_URL, gu_code, deal_ym, TRADE_FIELD_MAP)


def fetch_apt_rent(gu_code: str, deal_ym: str) -> pd.DataFrame:
    """단일 구/월 아파트 전월세 실거래 데이터를 조회한다."""
    return _call_api(APT_RENT_URL, gu_code, deal_ym, RENT_FIELD_MAP)


def _cache_path(data_type: str, gu_code: str, ym: str) -> str:
    """구+월 단위 캐시 파일 경로. 예: data/trade_11680_202501.csv"""
    return os.path.join(DATA_DIR, f"{data_type}_{gu_code}_{ym}.csv")


def _collect_data(
    fetch_fn,
    data_type: str,
    start_ym: str,
    end_ym: str,
    gu_codes: list[str] | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """구+월 단위로 개별 캐싱하며 데이터를 수집한다.

    - 확정 데이터 (2개월+ 전): 영구 캐시
    - 준확정 (1~2개월 전): 7일 후 재수집
    - 미확정 (당월): 1일 후 재수집
    - force_refresh=True: 모든 캐시 무시하고 재수집
    """
    if gu_codes is None:
        gu_codes = list(SEOUL_GU_CODES.keys())

    os.makedirs(DATA_DIR, exist_ok=True)
    months = _generate_months(start_ym, end_ym)
    meta = _load_meta()
    frames = []
    meta_changed = False

    for gu_code in gu_codes:
        for ym in months:
            cache_file = _cache_path(data_type, gu_code, ym)
            cache_key = f"{data_type}_{gu_code}_{ym}"

            # --- 캐시 판단 ---
            need_fetch = False

            if force_refresh:
                need_fetch = True
            elif not os.path.exists(cache_file):
                need_fetch = True
            elif os.path.getsize(cache_file) < 10:
                # 빈/손상 캐시 — 재수집 대상
                need_fetch = True
            elif _cache_expired(cache_key, ym, meta):
                need_fetch = True

            if not need_fetch:
                # 캐시 사용
                try:
                    cached = pd.read_csv(cache_file, encoding="utf-8-sig")
                except (pd.errors.EmptyDataError, pd.errors.ParserError):
                    need_fetch = True
                else:
                    if not cached.empty:
                        frames.append(cached)
                    continue

            if not need_fetch:
                continue

            # --- API 호출 ---
            df = fetch_fn(gu_code, ym)
            if not df.empty:
                df.to_csv(cache_file, index=False, encoding="utf-8-sig")
                frames.append(df)
            else:
                # 빈 결과도 기록 (재호출 방지, 단 당월은 TTL로 다시 시도)
                pd.DataFrame().to_csv(cache_file, index=False)

            # 메타 업데이트
            meta[cache_key] = datetime.now().isoformat()
            meta_changed = True
            time.sleep(0.3)

    if meta_changed:
        _save_meta(meta)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def collect_seoul_data(
    start_ym: str, end_ym: str,
    gu_codes: list[str] | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """서울 매매 실거래 데이터를 수집한다."""
    return _collect_data(fetch_apt_trade, "trade", start_ym, end_ym, gu_codes, force_refresh)


def collect_seoul_rent_data(
    start_ym: str, end_ym: str,
    gu_codes: list[str] | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """서울 전월세 실거래 데이터를 수집한다."""
    return _collect_data(fetch_apt_rent, "rent", start_ym, end_ym, gu_codes, force_refresh)


def get_cache_status() -> dict:
    """현재 캐시 상태를 요약한다.

    Returns:
        {
            "total_files": int,
            "total_size_mb": float,
            "oldest": str (ISO),
            "newest": str (ISO),
            "stale_count": int,  -- TTL 만료된 캐시 수
        }
    """
    meta = _load_meta()
    now = datetime.now()
    total_files = 0
    total_size = 0
    stale_count = 0
    timestamps = []

    if not os.path.exists(DATA_DIR):
        return {"total_files": 0, "total_size_mb": 0, "oldest": "-", "newest": "-", "stale_count": 0}

    for f in os.listdir(DATA_DIR):
        if f.endswith(".csv") and ("trade_" in f or "rent_" in f):
            total_files += 1
            total_size += os.path.getsize(os.path.join(DATA_DIR, f))

            # 파일명에서 ym 추출
            parts = f.replace(".csv", "").split("_")
            if len(parts) >= 3:
                ym = parts[-1]
                cache_key = f.replace(".csv", "")
                if _cache_expired(cache_key, ym, meta):
                    stale_count += 1

            ts = meta.get(f.replace(".csv", ""))
            if ts:
                timestamps.append(ts)

    return {
        "total_files": total_files,
        "total_size_mb": round(total_size / 1024 / 1024, 1),
        "oldest": min(timestamps)[:10] if timestamps else "-",
        "newest": max(timestamps)[:10] if timestamps else "-",
        "stale_count": stale_count,
    }


def _generate_months(start_ym: str, end_ym: str) -> list[str]:
    """시작~종료 년월 사이의 YYYYMM 리스트를 생성한다."""
    sy, sm = int(start_ym[:4]), int(start_ym[4:6])
    ey, em = int(end_ym[:4]), int(end_ym[4:6])

    months = []
    y, m = sy, sm
    while y * 100 + m <= ey * 100 + em:
        months.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def save_to_csv(df: pd.DataFrame, filename: str) -> str:
    """DataFrame을 data/ 디렉터리에 CSV로 저장한다."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def load_from_csv(filename: str) -> pd.DataFrame:
    """data/ 디렉터리에서 CSV를 로드한다. 파일이 없으면 빈 DataFrame."""
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame()


if __name__ == "__main__":
    # 캐시 상태 확인
    status = get_cache_status()
    print(f"캐시 파일: {status['total_files']}개 / {status['total_size_mb']}MB")
    print(f"수집 기간: {status['oldest']} ~ {status['newest']}")
    print(f"갱신 필요: {status['stale_count']}개")

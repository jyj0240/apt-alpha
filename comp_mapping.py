"""비교군 매핑 로더.

data/comp_groups.json 을 읽어 두 가지를 제공한다:
- comparable_dongs(gu, dong): 구 경계를 넘는 동급/인접 동 목록 (없으면 자기 자신만).
- cluster_for(apt): 시장 대장 단지 클러스터 매칭 (단지명 contains, 보조용).
"""

import json
import os

import pandas as pd

from config import DATA_DIR

_FILE = os.path.join(DATA_DIR, "comp_groups.json")


def _load() -> dict:
    try:
        with open(_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"dong_groups": [], "complex_clusters": []}


_DATA = _load()

# (구, 동) -> (그룹명, [(구,동), ...])
_DONG_INDEX: dict[tuple, tuple] = {}
for _g in _DATA.get("dong_groups", []):
    _pairs = [tuple(d) for d in _g.get("dongs", [])]
    for _p in _pairs:
        _DONG_INDEX[_p] = (_g.get("name", ""), _pairs)


def _norm(s: str) -> str:
    return str(s).replace(" ", "").replace("(", "").replace(")", "").lower()


def comparable_dongs(gu: str, dong: str) -> tuple[list[tuple], str | None, bool]:
    """비교 대상 (구, 동) 목록을 반환한다.

    Returns:
        (pairs, group_name, mapped)
        - pairs: 자기 자신을 맨 앞에 둔 (구, 동) 목록.
        - group_name: 매핑된 동 그룹 이름 (없으면 None).
        - mapped: 매핑 존재 여부. False면 호출측이 같은 구 fallback을 쓰면 됨.
    """
    hit = _DONG_INDEX.get((gu, dong))
    if not hit:
        return [(gu, dong)], None, False
    name, pairs = hit
    ordered = [(gu, dong)] + [p for p in pairs if p != (gu, dong)]
    seen, res = set(), []
    for p in ordered:
        if p not in seen:
            seen.add(p)
            res.append(p)
    return res, name, True


def cluster_for(apt: str) -> tuple[str | None, set]:
    """단지명이 속한 대장 클러스터를 찾는다.

    Returns:
        (cluster_name, {정규화된 멤버 단지명 키 집합}). 없으면 (None, set()).
    """
    na = _norm(apt)
    if not na:
        return None, set()
    for c in _DATA.get("complex_clusters", []):
        keys = {_norm(m["apt"]) for m in c.get("members", [])}
        for k in keys:
            if k and (k in na or na in k):
                return c.get("name"), keys
    return None, set()


def find_comparables_across(
    df_pool: pd.DataFrame,
    target_gu: str,
    target_dong: str,
    target_apt: str,
    target_build_year: int,
    target_area: float,
    cluster_keys: set | None = None,
    max_results: int = 12,
) -> pd.DataFrame:
    """구 경계를 넘나드는 후보 풀(df_pool)에서 비교 단지를 선별한다.

    호출측이 비교군 매핑으로 이미 좁혀 둔 (구, 동) 풀이라고 가정한다.

    - 타겟: 같은 구·동·단지, 면적 ±15㎡, 거래 3건+ (신축도 잡히게 완화).
    - 클러스터 멤버(cluster_keys): 연식 무관 포함 (거래 3건+).
    - 그 외 후보: 면적 ±15㎡, 연식 ±7년, 거래 5건+.

    Returns:
        gu_name, dong, apt_name, build_year, median_price, median_sqm,
        trade_count, change_pct, is_target 컬럼. median_sqm 내림차순.
    """
    if df_pool.empty:
        return pd.DataFrame()

    keys = cluster_keys or set()
    area_low, area_high = target_area - 15, target_area + 15

    results = []
    for (gu, dong, apt), group in df_pool.groupby(["gu_name", "dong", "apt_name"]):
        area_filtered = group[(group["area"] >= area_low) & (group["area"] <= area_high)]
        is_target = (gu == target_gu and dong == target_dong and apt == target_apt)
        is_cluster = _norm(apt) in keys if keys else False

        min_trades = 3 if (is_target or is_cluster) else 5
        if len(area_filtered) < min_trades:
            continue

        by = area_filtered["build_year"].median()
        if not is_target and not is_cluster:
            if pd.isna(by) or abs(by - target_build_year) > 7:
                continue

        history = area_filtered.groupby("ym")["price"].median().sort_index()
        change_pct = 0.0
        if len(history) >= 2:
            change_pct = round((history.iloc[-1] - history.iloc[0]) / history.iloc[0] * 100, 1)

        results.append({
            "gu_name": gu,
            "dong": dong,
            "apt_name": apt,
            "build_year": int(by) if not pd.isna(by) else 0,
            "median_price": int(area_filtered["price"].median()),
            "median_sqm": round(area_filtered["price_per_sqm"].median(), 1),
            "trade_count": len(area_filtered),
            "change_pct": change_pct,
            "is_target": is_target,
        })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results).sort_values("median_sqm", ascending=False)
    target_rows = df[df["is_target"]]
    others = df[~df["is_target"]].head(max_results)
    return pd.concat([target_rows, others], ignore_index=True)

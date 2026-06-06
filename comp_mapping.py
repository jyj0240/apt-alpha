"""비교군 매핑 로더.

data/comp_groups.json 을 읽어 두 가지를 제공한다:
- comparable_dongs(gu, dong): 구 경계를 넘는 동급/인접 동 목록 (없으면 자기 자신만).
- cluster_for(apt): 시장 대장 단지 클러스터 매칭 (단지명 contains, 보조용).
"""

import json
import os

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

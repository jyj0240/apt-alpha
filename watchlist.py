"""관심 단지(watchlist) 영속 저장.

세션이 아니라 파일(data/watchlist.json)에 저장해 새로고침해도 유지된다.
(Streamlit Cloud에서는 컨테이너 재배포 시 초기화될 수 있음 — 현재 단일 사용자 가정.)

항목 형식: {"gu": 구, "dong": 동, "apt": 단지명, "area": 전용면적(int)}
"""

import json
import os

from config import DATA_DIR

_WL_FILE = os.path.join(DATA_DIR, "watchlist.json")


def key_of(item: dict) -> str:
    """관심 단지 항목의 고유 키."""
    return f"{item['gu']}|{item['dong']}|{item['apt']}|{item['area']}"


def load_watchlist() -> list[dict]:
    if os.path.exists(_WL_FILE):
        try:
            with open(_WL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save(items: list[dict]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_WL_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def add_to_watchlist(item: dict) -> list[dict]:
    items = load_watchlist()
    if key_of(item) not in {key_of(x) for x in items}:
        items.insert(0, item)  # 최근 등록이 맨 위
        _save(items)
    return items


def remove_from_watchlist(key: str) -> list[dict]:
    items = [x for x in load_watchlist() if key_of(x) != key]
    _save(items)
    return items

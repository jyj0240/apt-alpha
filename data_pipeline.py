"""공용 데이터 파이프라인.

기존 페이지(1·8·9·10 등)가 똑같이 반복하던 패턴 —

    codes = [GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE]
    raw = collect_seoul_data(s_ym, e_ym, codes)
    df = clean_trade_data(raw)
    df = add_area_category(df)
    df = filter_by_area(df, area)
    df = filter_by_build_year(df, build_year)
    df = filter_outliers(df, exclude_outliers)

— 를 load_trade() / load_rent() 한 번 호출로 대체한다. 캐싱(@st.cache_data)도
이 모듈에서 일괄 관리하여 페이지마다 중복 정의하던 get_data 함수를 없앤다.

백엔드(data_collector / data_processor)는 변경하지 않는다. 표현 계층의 중복 제거 목적.
"""

import streamlit as st

from config import GU_NAME_TO_CODE
from data_collector import collect_seoul_data, collect_seoul_rent_data
from data_processor import (
    clean_trade_data,
    clean_rent_data,
    add_area_category,
    filter_by_area,
    filter_by_build_year,
    filter_outliers,
)


def _codes(gus) -> tuple[str, ...]:
    """구 이름 리스트 → 법정동 코드 튜플 (캐시 키로 쓰기 위해 정렬·튜플)."""
    return tuple(sorted(GU_NAME_TO_CODE[g] for g in gus if g in GU_NAME_TO_CODE))


@st.cache_data(show_spinner="데이터 수집 중...")
def _collect_trade(codes: tuple | None, s_ym: str, e_ym: str):
    """매매 원시 데이터 수집 (캐시). codes=None이면 서울 전체."""
    return collect_seoul_data(s_ym, e_ym, list(codes) if codes else None)


@st.cache_data(show_spinner="전월세 데이터 수집 중...")
def _collect_rent(codes: tuple | None, s_ym: str, e_ym: str):
    """전월세 원시 데이터 수집 (캐시). codes=None이면 서울 전체."""
    return collect_seoul_rent_data(s_ym, e_ym, list(codes) if codes else None)


def current_filters() -> dict:
    """session_state에 저장된 공통 필터를 딕셔너리로 읽어온다.

    홈/사이드바에서 설정한 값을 페이지가 일관되게 꺼내 쓰기 위한 단일 진입점.
    """
    ss = st.session_state
    return {
        "gus": ss.get("selected_gus", []),
        "start_ym": ss.get("start_ym", "202401"),
        "end_ym": ss.get("end_ym", "202412"),
        "area": ss.get("selected_area", "전체"),
        "build_year": ss.get("selected_build_year", "전체"),
        "exclude_outliers": ss.get("exclude_outliers", True),
    }


def load_trade(
    gus,
    start_ym: str,
    end_ym: str,
    *,
    area: str | None = "전체",
    build_year: str | None = "전체",
    exclude_outliers: bool = True,
    all_seoul: bool = False,
):
    """매매 데이터를 수집·정제·필터까지 한 번에 반환한다.

    Args:
        gus: 구 이름 리스트.
        start_ym, end_ym: 조회 기간 (YYYYMM).
        area: 면적대 필터. None이면 면적 필터 건너뜀.
        build_year: 연식 필터. None이면 연식 필터 건너뜀.
        exclude_outliers: 이상치 제외 여부.
        all_seoul: True이면 gus를 무시하고 서울 25개 구 전체를 수집
                   (알파/베타 팩터 구축 등 시장 전체가 필요할 때).

    Returns:
        정제·필터된 DataFrame. 데이터가 없으면 빈 DataFrame.
    """
    codes = None if all_seoul else _codes(gus)
    raw = _collect_trade(codes, start_ym, end_ym)
    if raw.empty:
        return raw

    df = clean_trade_data(raw)
    df = add_area_category(df)
    if area is not None:
        df = filter_by_area(df, area)
    if build_year is not None:
        df = filter_by_build_year(df, build_year)
    df = filter_outliers(df, exclude_outliers)
    return df


def load_rent(
    gus,
    start_ym: str,
    end_ym: str,
    *,
    all_seoul: bool = False,
):
    """전월세 데이터를 수집·정제하여 반환한다.

    전월세는 매매와 달리 면적/연식 필터를 기본 적용하지 않는다
    (전세가율 등 집계 단계에서 처리). 데이터가 없으면 빈 DataFrame.
    """
    codes = None if all_seoul else _codes(gus)
    raw = _collect_rent(codes, start_ym, end_ym)
    if raw.empty:
        return raw
    return clean_rent_data(raw)

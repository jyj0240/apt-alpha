import streamlit as st
from datetime import datetime, timedelta

from config import SEOUL_GU_CODES, AREA_CATEGORIES
from app_defaults import DEFAULT_GUS, DEFAULT_AREA, DEFAULT_START_YM


def _build_year_options() -> list[str]:
    cur = datetime.today().year
    return [
        "전체",
        f"신축 {cur - 5}~",
        f"준신축 {cur - 10}~{cur - 5}",
        f"중축 {cur - 20}~{cur - 10}",
        f"구축 ~{cur - 20}",
    ]


def _default_yms() -> tuple[str, str]:
    today = datetime.today()
    last_month = today.replace(day=1) - timedelta(days=1)
    end = last_month.strftime("%Y%m")
    return DEFAULT_START_YM, end


def render_sidebar_filters() -> dict:
    with st.sidebar:
        st.markdown(
            "<p style='color:#2563eb; font-weight:700; font-size:0.8rem; "
            "letter-spacing:1px; margin-bottom:10px;'>FILTERS</p>",
            unsafe_allow_html=True,
        )

        default_start, default_end = _default_yms()

        # 홈에서 설정한 값을 위젯 key에 동기화 (key가 있으면 default 무시하므로)
        if "selected_gus" in st.session_state and "sb_selected_gus" not in st.session_state:
            st.session_state["sb_selected_gus"] = st.session_state["selected_gus"]

        # 지역
        gu_names = list(SEOUL_GU_CODES.values())
        selected_gus = st.multiselect(
            "분석 지역", gu_names,
            default=st.session_state.get("selected_gus", list(DEFAULT_GUS)),
            key="sb_selected_gus",
        )

        # 기간 — 시작/종료 각각 2열 (한 줄에 년+월)
        cur_year = datetime.today().year
        year_range = list(range(2020, cur_year + 1))
        month_range = list(range(1, 13))

        def _parse_ym(ym_str, fy, fm):
            try:
                return int(ym_str[:4]), int(ym_str[4:6])
            except (ValueError, IndexError):
                return fy, fm

        prev_start = st.session_state.get("start_ym", default_start)
        prev_end = st.session_state.get("end_ym", default_end)
        def_sy, def_sm = _parse_ym(prev_start, cur_year - 1, 1)
        def_ey, def_em = _parse_ym(prev_end, cur_year, datetime.today().month)

        # 홈에서 설정한 기간을 위젯 key에 동기화
        if "sb_sy" not in st.session_state:
            st.session_state["sb_sy"] = def_sy
            st.session_state["sb_sm"] = def_sm
            st.session_state["sb_ey"] = def_ey
            st.session_state["sb_em"] = def_em

        st.caption("시작")
        s1, s2 = st.columns(2)
        start_year = s1.selectbox(
            "시작년", year_range,
            index=year_range.index(def_sy) if def_sy in year_range else 0,
            key="sb_sy", label_visibility="collapsed",
            format_func=lambda y: f"{y}",
        )
        start_month = s2.selectbox(
            "시작월", month_range,
            index=month_range.index(def_sm) if def_sm in month_range else 0,
            key="sb_sm", label_visibility="collapsed",
            format_func=lambda m: f"{m}월",
        )

        st.caption("종료")
        e1, e2 = st.columns(2)
        end_year = e1.selectbox(
            "종료년", year_range,
            index=year_range.index(def_ey) if def_ey in year_range else len(year_range) - 1,
            key="sb_ey", label_visibility="collapsed",
            format_func=lambda y: f"{y}",
        )
        end_month = e2.selectbox(
            "종료월", month_range,
            index=month_range.index(def_em) if def_em in month_range else 0,
            key="sb_em", label_visibility="collapsed",
            format_func=lambda m: f"{m}월",
        )

        start_ym = f"{start_year}{start_month:02d}"
        end_ym = f"{end_year}{end_month:02d}"

        if start_ym > end_ym:
            st.warning("시작이 종료보다 늦습니다.")

        # 면적대 — 홈에서 설정한 값 동기화
        area_options = ["전체"] + list(AREA_CATEGORIES.keys())
        if "sb_area" not in st.session_state and "selected_area" in st.session_state:
            home_area = st.session_state["selected_area"]
            if home_area in area_options:
                st.session_state["sb_area"] = home_area

        selected_area = st.selectbox(
            "면적대", area_options,
            index=area_options.index(st.session_state.get("selected_area", DEFAULT_AREA))
            if st.session_state.get("selected_area", DEFAULT_AREA) in area_options else 0,
            key="sb_area",
        )

        # 연식 — 홈에서 설정한 값 동기화
        build_year_options = _build_year_options()
        if "sb_build" not in st.session_state and "selected_build_year" in st.session_state:
            home_build = st.session_state["selected_build_year"]
            if home_build in build_year_options:
                st.session_state["sb_build"] = home_build

        selected_build_year = st.selectbox(
            "연식", build_year_options,
            index=build_year_options.index(
                st.session_state.get("selected_build_year", "전체")
            ) if st.session_state.get("selected_build_year", "전체") in build_year_options else 0,
            key="sb_build",
        )

        # 아웃라이어 필터
        exclude_outliers = st.checkbox(
            "아웃라이어 제외",
            value=st.session_state.get("exclude_outliers", True),
            key="sb_outlier",
            help="같은 단지+면적대 중위가 대비 40% 이상 이탈 거래 제외",
        )

        # session_state
        st.session_state["selected_gus"] = selected_gus
        st.session_state["start_ym"] = start_ym
        st.session_state["end_ym"] = end_ym
        st.session_state["selected_area"] = selected_area
        st.session_state["selected_build_year"] = selected_build_year
        st.session_state["exclude_outliers"] = exclude_outliers

        # 전문가 모드 — 알파/베타/변동성 등 Pro 지표 펼침 제어
        pro_mode = st.toggle(
            "전문가 모드",
            value=st.session_state.get("pro_mode", False),
            key="sb_pro_mode",
            help="끄면 쉬운 핵심만, 켜면 알파·베타·변동성 등 전문 지표까지 펼쳐 보여줍니다.",
        )
        st.session_state["pro_mode"] = pro_mode

        st.divider()

        # 데이터 갱신 버튼 + 캐시 상태
        from data_collector import get_cache_status
        status = get_cache_status()

        st.markdown(
            "<p style='color:#2563eb; font-weight:700; font-size:0.8rem; "
            "letter-spacing:1px; margin-bottom:8px;'>DATA</p>",
            unsafe_allow_html=True,
        )

        st.caption(
            f"캐시 {status['total_files']}개 / {status['total_size_mb']}MB\n\n"
            f"최신 수집: {status['newest']}"
        )

        if status["stale_count"] > 0:
            st.caption(f"갱신 대기: {status['stale_count']}개")

        if st.button("데이터 갱신", use_container_width=True, key="sb_refresh"):
            st.session_state["force_refresh"] = True
            st.rerun()

        st.markdown(
            "<p style='font-size:0.65rem; color:#94a3b8; margin-top:4px;'>"
            "당월: 1일 / 전월: 7일 / 2개월+: 영구 캐시</p>",
            unsafe_allow_html=True,
        )

    # force_refresh 처리: 버튼 누르면 Streamlit 캐시 클리어 후 리셋
    if st.session_state.get("force_refresh"):
        st.cache_data.clear()
        st.session_state["force_refresh"] = False

    return {
        "selected_gus": selected_gus,
        "start_ym": start_ym,
        "end_ym": end_ym,
        "selected_area": selected_area,
        "selected_build_year": selected_build_year,
    }

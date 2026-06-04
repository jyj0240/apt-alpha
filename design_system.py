"""통일된 디자인 시스템: 컬러 팔레트, 한국어 포맷터, hover 템플릿, 차트 팩토리."""

import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# 1. 컬러 팔레트
# ---------------------------------------------------------------------------

COLORS = {
    "primary": "#2563eb",
    "primary_light": "#93c5fd",
    "primary_dark": "#1d4ed8",
    "accent": "#7c3aed",
    "up": "#16a34a",
    "down": "#dc2626",
    "neutral": "#64748b",
    "warning": "#f59e0b",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "border": "#e2e8f0",
    "text_primary": "#0f172a",
    "text_secondary": "#64748b",
    "grid": "#f1f5f9",
    "zeroline": "#e2e8f0",
    "axis_line": "#cbd5e1",
}

# 다중 구 비교용 10색 팔레트 (색각 이상 고려, 구분도 높은 조합)
CATEGORICAL_10 = [
    "#2563eb",  # blue
    "#dc2626",  # red
    "#16a34a",  # green
    "#f59e0b",  # amber
    "#7c3aed",  # violet
    "#0891b2",  # cyan
    "#db2777",  # pink
    "#65a30d",  # lime
    "#ea580c",  # orange
    "#6366f1",  # indigo
]

# choropleth / 히트맵용 순차 블루 스케일
SEQUENTIAL_BLUES = [
    "#eff6ff", "#bfdbfe", "#93c5fd", "#60a5fa", "#3b82f6", "#1d4ed8",
]

# 상승/하락 양극 스케일 (Red-White-Blue)
DIVERGING_RdBu = [
    "#dc2626", "#f87171", "#fca5a5", "#ffffff", "#93c5fd", "#3b82f6", "#1d4ed8",
]

# ---------------------------------------------------------------------------
# 2. 차트 테마 설정
# ---------------------------------------------------------------------------

CHART_LAYOUT = dict(
    template="plotly_white",
    paper_bgcolor=COLORS["surface"],
    plot_bgcolor=COLORS["surface"],
    font=dict(color=COLORS["text_primary"], size=11),
    legend=dict(
        bgcolor="rgba(255,255,255,0.8)",
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0,
        font=dict(size=10),
    ),
    margin=dict(l=45, r=8, t=40, b=30),
)


def apply_theme(fig: go.Figure) -> go.Figure:
    """공통 라이트 테마를 적용한다."""
    fig.update_layout(**CHART_LAYOUT)
    fig.update_xaxes(
        gridcolor=COLORS["grid"],
        zerolinecolor=COLORS["zeroline"],
        showgrid=True,
        linecolor=COLORS["axis_line"],
        tickfont=dict(size=9),
        tickangle=0,
        title_font=dict(size=10),
        nticks=8,
    )
    fig.update_yaxes(
        gridcolor=COLORS["grid"],
        zerolinecolor=COLORS["zeroline"],
        showgrid=True,
        linecolor=COLORS["axis_line"],
        tickfont=dict(size=9),
        title_font=dict(size=10),
        title_standoff=5,
    )
    return fig


def create_figure(**layout_kwargs) -> go.Figure:
    """go.Figure()를 생성하고 공통 테마를 자동 적용한다."""
    fig = go.Figure()
    fig = apply_theme(fig)
    if layout_kwargs:
        fig.update_layout(**layout_kwargs)
    return fig


# ---------------------------------------------------------------------------
# 3. 한국어 가격/수치 포맷터
# ---------------------------------------------------------------------------

def format_price(val_man: float) -> str:
    """만원 단위 값을 한국어 가격 문자열로 변환.

    85000 → '8억 5,000만원'
    5000  → '5,000만원'
    120000 → '12억'
    -3000 → '-3,000만원'
    """
    if val_man is None or val_man != val_man:  # NaN check
        return "N/A"

    negative = val_man < 0
    val = abs(val_man)

    eok = int(val // 10000)
    man = int(val % 10000)

    if eok > 0 and man > 0:
        result = f"{eok}억 {man:,}만원"
    elif eok > 0:
        result = f"{eok}억"
    else:
        result = f"{man:,}만원"

    return f"-{result}" if negative else result


def format_sqm_price(val_man: float) -> str:
    """m2당 단가 포맷: '158.3만원/m2'."""
    if val_man is None or val_man != val_man:
        return "N/A"
    return f"{val_man:,.1f}만원/m2"


# 하위 호환성
format_pyeong_price = format_sqm_price


def format_pct(val: float, with_sign: bool = True) -> str:
    """퍼센트 포맷: '+3.2%' 또는 '-1.5%'."""
    if val is None or val != val:
        return "N/A"
    if with_sign:
        return f"{val:+.1f}%"
    return f"{val:.1f}%"


def format_count(val: int) -> str:
    """건수 포맷: '1,234건'."""
    if val is None:
        return "N/A"
    return f"{int(val):,}건"


# ---------------------------------------------------------------------------
# 4. Hover 템플릿 팩토리
# ---------------------------------------------------------------------------

def hover_price_trend() -> str:
    """시계열 가격 차트용 hover 템플릿.

    customdata[0] = 구이름, customdata[1] = 포맷된 가격 문자열
    """
    return (
        "<b>%{customdata[0]}</b><br>"
        "%{x}<br>"
        "%{customdata[1]}<extra></extra>"
    )


def hover_sqm_trend() -> str:
    """m2당 단가 시계열 차트용.

    customdata[0] = 구이름, customdata[1] = 포맷된 m2당 단가 문자열
    """
    return (
        "<b>%{customdata[0]}</b><br>"
        "%{x}<br>"
        "%{customdata[1]}<extra></extra>"
    )


# 하위 호환성
hover_pyeong_trend = hover_sqm_trend


def hover_volume() -> str:
    """거래량 차트용.

    customdata[0] = 구이름
    """
    return (
        "<b>%{customdata[0]}</b><br>"
        "%{x}<br>"
        "%{y}건<extra></extra>"
    )


def hover_scatter_apt() -> str:
    """산점도용 (아파트 정보).

    customdata[0] = 단지명, customdata[1] = 동, customdata[2] = 층,
    customdata[3] = 포맷된 가격
    """
    return (
        "<b>%{customdata[0]}</b><br>"
        "%{customdata[1]}<br>"
        "%{customdata[2]}층 / %{x:.1f}m2<br>"
        "%{customdata[3]}<extra></extra>"
    )


def hover_bar_ranking() -> str:
    """랭킹 바차트용.

    customdata[0] = 구이름 또는 라벨
    """
    return (
        "<b>%{customdata[0]}</b><br>"
        "%{x}<extra></extra>"
    )


def hover_gap_chart() -> str:
    """매매-전세 갭 차트용.

    customdata[0] = 매매가 포맷, customdata[1] = 전세가 포맷,
    customdata[2] = 갭 포맷
    """
    return (
        "%{x}<br>"
        "매매: %{customdata[0]}<br>"
        "전세: %{customdata[1]}<br>"
        "갭: %{customdata[2]}<extra></extra>"
    )


# ---------------------------------------------------------------------------
# 5. 공통 annotation 헬퍼
# ---------------------------------------------------------------------------

def calc_table_height(n_rows: int, row_height: int = 35, header: int = 38,
                      min_h: int = 200, max_h: int = 1200) -> int:
    """데이터프레임 행 수 기반 적정 높이를 계산한다."""
    h = header + n_rows * row_height + 2
    return max(min_h, min(h, max_h))


def add_last_point_label(fig: go.Figure, x_vals, y_vals, label: str,
                         color: str = COLORS["text_primary"]) -> go.Figure:
    """시계열 차트의 마지막 데이터 포인트에 값 레이블을 추가한다."""
    if len(x_vals) == 0 or len(y_vals) == 0:
        return fig
    fig.add_annotation(
        x=x_vals[-1],
        y=y_vals[-1],
        text=label,
        showarrow=False,
        font=dict(size=10, color=color, weight="bold"),
        xanchor="left",
        xshift=8,
    )
    return fig


def add_reference_line(fig: go.Figure, orientation: str = "h",
                       value: float = 0, label: str = "",
                       color: str = COLORS["neutral"],
                       dash: str = "dash") -> go.Figure:
    """수평 또는 수직 참조선을 추가한다."""
    if orientation == "h":
        fig.add_hline(y=value, line_dash=dash, line_color=color,
                      annotation_text=label, annotation_font_color=color)
    else:
        fig.add_vline(x=value, line_dash=dash, line_color=color,
                      annotation_text=label, annotation_font_color=color)
    return fig

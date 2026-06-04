import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from design_system import (
    COLORS,
    CATEGORICAL_10,
    apply_theme,
    create_figure,
    format_price,
    format_sqm_price,
    format_pct,
    hover_price_trend,
    hover_sqm_trend,
    hover_volume,
    hover_scatter_apt,
    add_last_point_label,
    add_reference_line,
)

# 하위 호환성: 기존 코드에서 _apply_theme 직접 호출하는 경우 대비
_apply_theme = apply_theme


def price_trend_chart(agg_df: pd.DataFrame, gu_names: list[str]) -> go.Figure:
    """구별 월별 중위 실거래가 시계열 차트."""
    filtered = agg_df[agg_df["gu_name"].isin(gu_names)].sort_values("ym")
    if filtered.empty:
        return go.Figure()

    fig = create_figure(
        title="구별 월별 중위 실거래가",
        xaxis_title="년월",
        yaxis_title="중위가격 (만원)",
        hovermode="x unified",
        xaxis_type="category",
    )

    for i, gu in enumerate(gu_names):
        gu_data = filtered[filtered["gu_name"] == gu]
        if gu_data.empty:
            continue
        color = CATEGORICAL_10[i % len(CATEGORICAL_10)]
        formatted_prices = [format_price(p) for p in gu_data["median_price"]]
        customdata = list(zip([gu] * len(gu_data), formatted_prices))

        fig.add_trace(go.Scatter(
            x=gu_data["ym"],
            y=gu_data["median_price"],
            name=gu,
            mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=5),
            customdata=customdata,
            hovertemplate=hover_price_trend(),
        ))

    return fig


def price_per_sqm_chart(agg_df: pd.DataFrame, gu_names: list[str]) -> go.Figure:
    """구별 월별 중위 m2당 단가 시계열 차트."""
    filtered = agg_df[agg_df["gu_name"].isin(gu_names)].sort_values("ym")
    if filtered.empty:
        return go.Figure()

    fig = create_figure(
        title="구별 월별 중위 m2당 가격",
        xaxis_title="년월",
        yaxis_title="m2당 가격 (만원/m2)",
        hovermode="x unified",
        xaxis_type="category",
    )

    # 선택 구 평균 참조선
    if not filtered.empty:
        seoul_avg = filtered.groupby("ym")["median_price_per_sqm"].mean()
        fig.add_trace(go.Scatter(
            x=seoul_avg.index,
            y=seoul_avg.values,
            name="선택 구 평균",
            mode="lines",
            line=dict(color=COLORS["neutral"], width=1.5, dash="dash"),
            hoverinfo="skip",
        ))

    for i, gu in enumerate(gu_names):
        gu_data = filtered[filtered["gu_name"] == gu]
        if gu_data.empty:
            continue
        color = CATEGORICAL_10[i % len(CATEGORICAL_10)]
        formatted = [format_sqm_price(p) for p in gu_data["median_price_per_sqm"]]
        customdata = list(zip([gu] * len(gu_data), formatted))

        fig.add_trace(go.Scatter(
            x=gu_data["ym"],
            y=gu_data["median_price_per_sqm"],
            name=gu,
            mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=5),
            customdata=customdata,
            hovertemplate=hover_sqm_trend(),
        ))

    return fig


# 하위 호환성
price_per_pyeong_chart = price_per_sqm_chart


def trade_volume_chart(agg_df: pd.DataFrame, gu_names: list[str]) -> go.Figure:
    """구별 월별 거래량 바 차트."""
    filtered = agg_df[agg_df["gu_name"].isin(gu_names)].sort_values("ym")
    if filtered.empty:
        return go.Figure()

    fig = create_figure(
        title="구별 월별 거래량",
        xaxis_title="년월",
        yaxis_title="거래 건수",
        barmode="group",
        xaxis_type="category",
    )

    for i, gu in enumerate(gu_names):
        gu_data = filtered[filtered["gu_name"] == gu]
        if gu_data.empty:
            continue
        color = CATEGORICAL_10[i % len(CATEGORICAL_10)]
        customdata = [[gu]] * len(gu_data)

        fig.add_trace(go.Bar(
            x=gu_data["ym"],
            y=gu_data["trade_count"],
            name=gu,
            marker_color=color,
            customdata=customdata,
            hovertemplate=hover_volume(),
            opacity=0.85,
        ))

    # 월별 총합 annotation (구가 2개 이상일 때)
    if len(gu_names) > 1:
        totals = filtered.groupby("ym")["trade_count"].sum()
        for ym, total in totals.items():
            fig.add_annotation(
                x=ym, y=total,
                text=f"{int(total)}",
                showarrow=False,
                font=dict(size=9, color=COLORS["text_secondary"]),
                yshift=12,
            )

    return fig


def area_price_scatter(df: pd.DataFrame, gu_name: str | None = None) -> go.Figure:
    """전용면적 vs 거래금액 산점도."""
    data = df.copy()
    if gu_name:
        data = data[data["gu_name"] == gu_name]
    if data.empty:
        return go.Figure()

    fig = create_figure(
        title="전용면적 vs 거래금액",
        xaxis_title="전용면적 (m2)",
        yaxis_title="거래금액 (만원)",
    )

    gu_list = data["gu_name"].unique()
    for i, gu in enumerate(gu_list):
        gu_data = data[data["gu_name"] == gu]
        color = CATEGORICAL_10[i % len(CATEGORICAL_10)]
        formatted_prices = [format_price(p) for p in gu_data["price"]]
        customdata = list(zip(
            gu_data["apt_name"].fillna(""),
            gu_data["dong"].fillna(""),
            gu_data["floor"].fillna(0).astype(int).astype(str),
            formatted_prices,
        ))

        fig.add_trace(go.Scatter(
            x=gu_data["area"],
            y=gu_data["price"],
            name=gu,
            mode="markers",
            marker=dict(color=color, size=6, opacity=0.5),
            customdata=customdata,
            hovertemplate=hover_scatter_apt(),
        ))

    # 중위값 참조선
    median_area = data["area"].median()
    median_price = data["price"].median()
    add_reference_line(fig, "v", median_area, f"면적 중위 {median_area:.0f}m2",
                       color=COLORS["neutral"], dash="dot")
    add_reference_line(fig, "h", median_price, f"가격 중위 {format_price(median_price)}",
                       color=COLORS["neutral"], dash="dot")

    return fig


def dong_comparison_chart(dong_df: pd.DataFrame, gu_name: str) -> go.Figure:
    """특정 구 내 동별 중위가격 비교 (최신 월)."""
    filtered = dong_df[dong_df["gu_name"] == gu_name]
    if filtered.empty:
        return go.Figure()

    latest_ym = filtered["ym"].max()
    latest = filtered[filtered["ym"] == latest_ym].sort_values(
        "median_price", ascending=True
    )
    if latest.empty:
        return go.Figure()

    gu_median = latest["median_price"].median()
    formatted_prices = [format_price(p) for p in latest["median_price"]]

    fig = create_figure(
        title=f"{gu_name} 동별 중위가격 ({latest_ym})",
        xaxis_title="중위가격 (만원)",
        yaxis_title="",
        height=max(300, len(latest) * 30),
    )

    # 구 평균 대비 색상 구분
    colors = [
        COLORS["primary"] if p >= gu_median else COLORS["primary_light"]
        for p in latest["median_price"]
    ]

    fig.add_trace(go.Bar(
        x=latest["median_price"],
        y=latest["dong"],
        orientation="h",
        marker_color=colors,
        text=formatted_prices,
        textposition="outside",
        textfont=dict(size=10),
    ))

    # 구 중위값 참조선
    add_reference_line(fig, "v", gu_median, f"구 중위 {format_price(gu_median)}",
                       color=COLORS["neutral"])

    return fig


# --- v2 차트 ---


def ranking_bar_chart(
    df: pd.DataFrame,
    value_col: str,
    label_col: str = "gu_name",
    title: str = "랭킹",
    value_label: str = "",
    color_positive: str = None,
    color_negative: str = None,
) -> go.Figure:
    """범용 수평 바차트 (랭킹용). 양수/음수에 따라 색상 구분."""
    c_pos = color_positive or COLORS["down"]  # 상승 = 빨강 (부동산 관례)
    c_neg = color_negative or COLORS["primary"]

    sorted_df = df.sort_values(value_col, ascending=True)

    colors = [
        c_pos if v >= 0 else c_neg
        for v in sorted_df[value_col]
    ]

    fig = go.Figure(
        go.Bar(
            x=sorted_df[value_col],
            y=sorted_df[label_col],
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.1f}%" for v in sorted_df[value_col]],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title=value_label or value_col,
        yaxis_title="",
        height=max(300, len(df) * 28),
    )
    return apply_theme(fig)


def volatility_heatmap(
    agg_df: pd.DataFrame, gu_names: list[str], value_col: str = "median_price"
) -> go.Figure:
    """구별 월별 변화율 히트맵."""
    filtered = agg_df[agg_df["gu_name"].isin(gu_names)].copy()
    if filtered.empty:
        return go.Figure()

    pivot_data = []
    for gu, group in filtered.groupby("gu_name"):
        sorted_g = group.sort_values("ym")
        sorted_g["pct_change"] = sorted_g[value_col].pct_change() * 100
        for _, row in sorted_g.iterrows():
            pivot_data.append({
                "gu_name": gu,
                "ym": row["ym"],
                "pct_change": round(row["pct_change"], 1) if pd.notna(row["pct_change"]) else 0,
            })

    pivot_df = pd.DataFrame(pivot_data)
    if pivot_df.empty:
        return go.Figure()

    pivot = pivot_df.pivot(index="gu_name", columns="ym", values="pct_change")

    fig = px.imshow(
        pivot,
        color_continuous_scale="RdBu_r",
        color_continuous_midpoint=0,
        title="구별 월간 가격 변화율 (%) 히트맵",
        labels={"color": "변화율 (%)"},
        aspect="auto",
    )
    fig.update_layout()
    return apply_theme(fig)


def scatter_matrix_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    label_col: str = "gu_name",
    title: str = "2x2 매트릭스",
    x_label: str = "",
    y_label: str = "",
) -> go.Figure:
    """2x2 매트릭스 산점도. 중앙선 + 사분면 배경 음영 + 레이블."""
    x_mid = df[x_col].median()
    y_mid = df[y_col].median()

    # x, y 범위 계산
    x_min = df[x_col].min()
    x_max = df[x_col].max()
    y_min = df[y_col].min()
    y_max = df[y_col].max()
    x_pad = (x_max - x_min) * 0.15 if x_max != x_min else 1
    y_pad = (y_max - y_min) * 0.15 if y_max != y_min else 1

    fig = create_figure(
        title=title,
        xaxis_title=x_label or x_col,
        yaxis_title=y_label or y_col,
        height=500,
        xaxis_range=[x_min - x_pad, x_max + x_pad],
        yaxis_range=[y_min - y_pad, y_max + y_pad],
    )

    # 사분면 배경 음영
    quadrants = [
        # 우상: 상승 + 높은 전세가율 (주의)
        (x_mid, x_max + x_pad, y_mid, y_max + y_pad, "rgba(239,68,68,0.06)"),
        # 좌상: 하락 + 높은 전세가율 (저평가 가능)
        (x_min - x_pad, x_mid, y_mid, y_max + y_pad, "rgba(37,99,235,0.06)"),
        # 우하: 상승 + 낮은 전세가율 (갭투자 부담)
        (x_mid, x_max + x_pad, y_min - y_pad, y_mid, "rgba(245,158,11,0.06)"),
        # 좌하: 시장 약세
        (x_min - x_pad, x_mid, y_min - y_pad, y_mid, "rgba(100,116,139,0.06)"),
    ]
    for x0, x1, y0, y1, fill_color in quadrants:
        fig.add_shape(
            type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
            fillcolor=fill_color, line=dict(width=0), layer="below",
        )

    # 사분면 레이블
    label_font = dict(size=10, color=COLORS["text_secondary"])
    fig.add_annotation(x=x_max + x_pad * 0.5, y=y_max + y_pad * 0.5, text="주의",
                       showarrow=False, font=label_font, opacity=0.7)
    fig.add_annotation(x=x_min - x_pad * 0.5, y=y_max + y_pad * 0.5, text="저평가?",
                       showarrow=False, font=label_font, opacity=0.7)
    fig.add_annotation(x=x_max + x_pad * 0.5, y=y_min - y_pad * 0.5, text="갭투자",
                       showarrow=False, font=label_font, opacity=0.7)
    fig.add_annotation(x=x_min - x_pad * 0.5, y=y_min - y_pad * 0.5, text="약세",
                       showarrow=False, font=label_font, opacity=0.7)

    # 데이터 포인트
    fig.add_trace(go.Scatter(
        x=df[x_col],
        y=df[y_col],
        text=df[label_col],
        mode="markers+text",
        textposition="top center",
        marker=dict(size=12, color=COLORS["primary"], line=dict(width=1, color="white")),
        textfont=dict(size=11, color=COLORS["text_primary"]),
        hovertemplate="<b>%{text}</b><br>"
                      + (x_label or x_col) + ": %{x:.1f}<br>"
                      + (y_label or y_col) + ": %{y:.1f}<extra></extra>",
    ))

    # 중앙선
    fig.add_vline(x=x_mid, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_hline(y=y_mid, line_dash="dash", line_color="gray", opacity=0.5)

    return fig


def sensitivity_chart(
    predictor,
    base_params: dict,
    vary_param: str,
    vary_range: list,
    param_label: str = "",
    base_value: float = None,
) -> go.Figure:
    """예측 모델 민감도 라인차트. 하나의 변수를 변화시키며 예측가 추이."""
    predictions = []
    for val in vary_range:
        params = base_params.copy()
        params[vary_param] = val
        pred = predictor.predict(**params)
        if pred is not None:
            predictions.append({"value": val, "predicted_price": pred})

    if not predictions:
        return go.Figure()

    pred_df = pd.DataFrame(predictions)
    formatted_prices = [format_price(p) for p in pred_df["predicted_price"]]

    fig = create_figure(
        title=f"{param_label or vary_param} 변화에 따른 예상 가격",
        xaxis_title=param_label or vary_param,
        yaxis_title="예상 가격 (만원)",
    )

    # fill under curve
    fig.add_trace(go.Scatter(
        x=pred_df["value"],
        y=pred_df["predicted_price"],
        mode="lines+markers",
        line=dict(color=COLORS["primary"], width=2.5),
        marker=dict(size=6),
        fill="tozeroy",
        fillcolor="rgba(37,99,235,0.08)",
        customdata=list(zip(formatted_prices)),
        hovertemplate=(
            f"{param_label or vary_param}: " + "%{x}<br>"
            "예상가: %{customdata[0]}<extra></extra>"
        ),
        name="예상 가격",
    ))

    # 현재값 마커 강조
    if base_value is not None:
        base_pred = None
        for row in predictions:
            if row["value"] == base_value:
                base_pred = row["predicted_price"]
                break
        if base_pred is not None:
            fig.add_trace(go.Scatter(
                x=[base_value],
                y=[base_pred],
                mode="markers",
                marker=dict(size=14, color=COLORS["accent"], symbol="diamond",
                            line=dict(width=2, color="white")),
                name="현재 입력값",
                hovertemplate=f"현재: {format_price(base_pred)}<extra></extra>",
            ))

    return fig

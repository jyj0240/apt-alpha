import pandas as pd

from config import SEOUL_GU_CODES, AREA_CATEGORIES


def clean_trade_data(df: pd.DataFrame) -> pd.DataFrame:
    """원시 거래 데이터를 정제한다."""
    if df.empty:
        return df

    df = df.copy()

    # 거래금액: 쉼표 제거 후 만원 단위 정수
    df["price"] = (
        df["price"].astype(str).str.replace(",", "").str.strip()
    )
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

    # 전용면적: float
    df["area"] = pd.to_numeric(df["area"], errors="coerce")

    # 층, 건축년도: 정수
    df["floor"] = pd.to_numeric(df["floor"], errors="coerce")
    df["build_year"] = pd.to_numeric(df["build_year"], errors="coerce")

    # 년/월/일 -> 날짜
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    df["day"] = pd.to_numeric(df["day"], errors="coerce")
    df["date"] = pd.to_datetime(
        df[["year", "month", "day"]].rename(
            columns={"year": "year", "month": "month", "day": "day"}
        ),
        errors="coerce",
    )
    df["ym"] = df["year"].astype("Int64").astype(str) + "-" + df["month"].astype("Int64").astype(str).str.zfill(2)

    # 구 이름 매핑 (CSV 로드 시 gu_code가 int로 읽힐 수 있으므로 str 변환)
    df["gu_name"] = df["gu_code"].astype(str).map(SEOUL_GU_CODES)

    # m2당 단가 (만원/m2)
    df["price_per_sqm"] = (df["price"] / df["area"]).round(1)

    # 결측치 제거
    df = df.dropna(subset=["price", "area"])

    # 아웃라이어 플래그
    df = flag_outliers(df)

    return df


OUTLIER_THRESHOLD = 0.40  # 중위가 대비 +-40% 이탈 시 아웃라이어


def flag_outliers(df: pd.DataFrame, threshold: float = OUTLIER_THRESHOLD) -> pd.DataFrame:
    """같은 단지+면적대 그룹 내 중위가 대비 이탈률로 아웃라이어를 플래그한다.

    추가 컬럼:
        is_outlier (bool): True면 아웃라이어
        outlier_reason (str): 판정 사유 ("" / "가격이탈" / "직거래+가격이탈")
    """
    if df.empty or "price" not in df.columns:
        df["is_outlier"] = False
        df["outlier_reason"] = ""
        return df

    df = df.copy()
    df["is_outlier"] = False
    df["outlier_reason"] = ""

    # 면적대가 아직 없을 수 있으므로 간이 분류
    if "area_category" not in df.columns:
        df["_area_bin"] = pd.cut(df["area"], bins=[0, 60, 85, 102, 135, 9999],
                                 labels=["s", "m1", "m2", "l1", "l2"], right=False)
    else:
        df["_area_bin"] = df["area_category"]

    # 그룹: 단지 + 면적 구간
    group_cols = ["apt_name", "_area_bin"]
    available = [c for c in group_cols if c in df.columns]
    if not available:
        df.drop(columns=["_area_bin"], errors="ignore", inplace=True)
        return df

    medians = df.groupby(available)["price"].transform("median")
    counts = df.groupby(available)["price"].transform("count")

    # 그룹 내 거래가 3건 미만이면 판정 불가 → 스킵
    has_enough = counts >= 3
    deviation = ((df["price"] - medians) / medians).abs()

    # 가격 이탈 판정
    price_outlier = has_enough & (deviation > threshold)
    df.loc[price_outlier, "is_outlier"] = True
    df.loc[price_outlier, "outlier_reason"] = "가격이탈"

    # 직거래 + 가격 이탈 (더 강한 신호)
    if "trade_type" in df.columns:
        is_direct = df["trade_type"].astype(str).str.contains("직거래", na=False)
        direct_outlier = is_direct & has_enough & (deviation > threshold * 0.7)  # 직거래는 28% 이탈부터
        df.loc[direct_outlier, "is_outlier"] = True
        df.loc[direct_outlier, "outlier_reason"] = "직거래+가격이탈"

    df.drop(columns=["_area_bin"], errors="ignore", inplace=True)
    return df


def filter_outliers(df: pd.DataFrame, exclude: bool = True) -> pd.DataFrame:
    """아웃라이어를 제외하거나 포함한다."""
    if not exclude or "is_outlier" not in df.columns:
        return df
    return df[~df["is_outlier"]].copy()


def categorize_area(area: float) -> str:
    """전용면적을 소형/중형/대형으로 분류한다."""
    for label, (low, high) in AREA_CATEGORIES.items():
        if low <= area < high:
            return label
    return "135m2~ 대형"


def add_area_category(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame에 면적대 컬럼을 추가한다."""
    df = df.copy()
    df["area_category"] = df["area"].apply(categorize_area)
    return df


def aggregate_by_gu_month(df: pd.DataFrame) -> pd.DataFrame:
    """구별/월별 중위가격, 평균가격, 거래량을 집계한다."""
    if df.empty:
        return df

    agg = (
        df.groupby(["gu_name", "ym"])
        .agg(
            median_price=("price", "median"),
            mean_price=("price", "mean"),
            median_price_per_sqm=("price_per_sqm", "median"),
            trade_count=("price", "count"),
        )
        .reset_index()
    )
    agg["median_price"] = agg["median_price"].round(0)
    agg["mean_price"] = agg["mean_price"].round(0)
    agg["median_price_per_sqm"] = agg["median_price_per_sqm"].round(0)
    return agg


def aggregate_by_apt(df: pd.DataFrame) -> pd.DataFrame:
    """단지별 요약 집계 (구/동/단지명 기준)."""
    if df.empty:
        return df

    agg = (
        df.groupby(["gu_name", "dong", "apt_name"])
        .agg(
            median_price=("price", "median"),
            median_price_per_sqm=("price_per_sqm", "median"),
            trade_count=("price", "count"),
            avg_build_year=("build_year", "mean"),
        )
        .reset_index()
    )
    agg["median_price"] = agg["median_price"].round(0)
    agg["median_price_per_sqm"] = agg["median_price_per_sqm"].round(0)
    agg["avg_build_year"] = agg["avg_build_year"].round(0)
    return agg


def get_apt_price_history(df: pd.DataFrame, apt_name: str) -> pd.DataFrame:
    """특정 단지의 ym별 중위가·m2당가·거래건수를 반환한다."""
    if df.empty:
        return df

    filtered = df[df["apt_name"] == apt_name]
    if filtered.empty:
        return filtered

    agg = (
        filtered.groupby("ym")
        .agg(
            median_price=("price", "median"),
            median_price_per_sqm=("price_per_sqm", "median"),
            trade_count=("price", "count"),
        )
        .reset_index()
        .sort_values("ym")
    )
    agg["median_price"] = agg["median_price"].round(0)
    agg["median_price_per_sqm"] = agg["median_price_per_sqm"].round(0)
    return agg


def aggregate_by_dong_month(df: pd.DataFrame) -> pd.DataFrame:
    """동별/월별 집계."""
    if df.empty:
        return df

    agg = (
        df.groupby(["gu_name", "dong", "ym"])
        .agg(
            median_price=("price", "median"),
            mean_price=("price", "mean"),
            trade_count=("price", "count"),
        )
        .reset_index()
    )
    agg["median_price"] = agg["median_price"].round(0)
    agg["mean_price"] = agg["mean_price"].round(0)
    return agg


def filter_by_area(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """면적대로 필터링한다."""
    if category == "전체":
        return df
    low, high = AREA_CATEGORIES.get(category, (0, 9999))
    return df[(df["area"] >= low) & (df["area"] < high)]


def filter_by_build_year(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """연식(준공연도)으로 필터링한다."""
    from datetime import datetime
    if category == "전체":
        return df
    cur = datetime.today().year
    ranges = {
        f"신축 {cur - 5}~":             (cur - 5,  cur + 1),
        f"준신축 {cur - 10}~{cur - 5}": (cur - 10, cur - 5),
        f"중축 {cur - 20}~{cur - 10}":  (cur - 20, cur - 10),
        f"구축 ~{cur - 20}":            (0,        cur - 20),
    }
    if category not in ranges:
        return df
    low, high = ranges[category]
    return df[df["build_year"].between(low, high - 1)]


def calc_apt_peak_drop(df: pd.DataFrame) -> pd.DataFrame:
    """단지별 전고점 대비 현재 중위가 하락률을 계산한다.

    Returns:
        gu_name, dong, apt_name, peak_price, peak_ym,
        current_price, current_ym, drop_pct 컬럼.
        drop_pct < 0 이면 하락, > 0 이면 전고점 경신.
    """
    if df.empty:
        return pd.DataFrame(columns=[
            "gu_name", "dong", "apt_name",
            "peak_price", "peak_ym", "current_price", "current_ym", "drop_pct",
        ])

    results = []
    for (gu, dong, apt_name), group in df.groupby(["gu_name", "dong", "apt_name"]):
        history = (
            group.groupby("ym")["price"]
            .median()
            .reset_index()
            .sort_values("ym")
        )
        if len(history) < 2:
            continue

        peak_idx = history["price"].idxmax()
        peak_price = int(history.loc[peak_idx, "price"])
        peak_ym = history.loc[peak_idx, "ym"]
        current_price = int(history["price"].iloc[-1])
        current_ym = history["ym"].iloc[-1]
        drop_pct = round((current_price - peak_price) / peak_price * 100, 1)

        results.append({
            "gu_name": gu, "dong": dong, "apt_name": apt_name,
            "peak_price": peak_price, "peak_ym": peak_ym,
            "current_price": current_price, "current_ym": current_ym,
            "drop_pct": drop_pct,
        })

    if not results:
        return pd.DataFrame(columns=[
            "gu_name", "dong", "apt_name",
            "peak_price", "peak_ym", "current_price", "current_ym", "drop_pct",
        ])
    return pd.DataFrame(results).sort_values("drop_pct")


def get_gu_summary(df: pd.DataFrame) -> pd.DataFrame:
    """구별 최신 월 요약 (지도용)."""
    if df.empty:
        return df

    latest_ym = df["ym"].max()
    latest = df[df["ym"] == latest_ym]

    summary = (
        latest.groupby("gu_name")
        .agg(
            median_price_per_sqm=("price_per_sqm", "median"),
            trade_count=("price", "count"),
            median_price=("price", "median"),
        )
        .reset_index()
    )
    summary["median_price_per_sqm"] = summary["median_price_per_sqm"].round(0)
    return summary


# --- 전월세 데이터 처리 ---


def clean_rent_data(df: pd.DataFrame) -> pd.DataFrame:
    """전월세 원시 데이터를 정제한다."""
    if df.empty:
        return df

    df = df.copy()

    # 보증금/월세: 쉼표 제거 후 숫자 변환 (만원 단위)
    for col in ["deposit", "monthly_rent"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(",", "").str.strip()
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 전용면적, 층, 건축년도
    df["area"] = pd.to_numeric(df["area"], errors="coerce")
    df["floor"] = pd.to_numeric(df["floor"], errors="coerce")
    df["build_year"] = pd.to_numeric(df["build_year"], errors="coerce")

    # 날짜
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    df["day"] = pd.to_numeric(df["day"], errors="coerce")
    df["date"] = pd.to_datetime(
        df[["year", "month", "day"]], errors="coerce"
    )
    df["ym"] = df["year"].astype("Int64").astype(str) + "-" + df["month"].astype("Int64").astype(str).str.zfill(2)

    # 구 이름 (CSV 로드 시 gu_code가 int로 읽힐 수 있으므로 str 변환)
    df["gu_name"] = df["gu_code"].astype(str).map(SEOUL_GU_CODES)

    # 전세/월세 구분: monthly_rent가 0이면 전세, 아니면 월세
    df["rent_type"] = df["monthly_rent"].apply(
        lambda x: "전세" if pd.notna(x) and x == 0 else "월세"
    )

    # 결측치 제거
    df = df.dropna(subset=["deposit", "area"])

    return df


def aggregate_rent_by_gu_month(df: pd.DataFrame) -> pd.DataFrame:
    """전월세 구별/월별 집계."""
    if df.empty:
        return df

    agg = (
        df.groupby(["gu_name", "ym", "rent_type"])
        .agg(
            median_deposit=("deposit", "median"),
            mean_deposit=("deposit", "mean"),
            median_monthly_rent=("monthly_rent", "median"),
            rent_count=("deposit", "count"),
        )
        .reset_index()
    )
    agg["median_deposit"] = agg["median_deposit"].round(0)
    agg["mean_deposit"] = agg["mean_deposit"].round(0)
    agg["median_monthly_rent"] = agg["median_monthly_rent"].round(0)
    return agg


def calc_jeonse_ratio(
    trade_agg: pd.DataFrame, rent_agg: pd.DataFrame
) -> pd.DataFrame:
    """구별/월별 전세가율을 계산한다 (전세 중위보증금 / 매매 중위가격).

    Returns:
        gu_name, ym, jeonse_ratio(%) 컬럼이 있는 DataFrame.
    """
    jeonse = rent_agg[rent_agg["rent_type"] == "전세"][
        ["gu_name", "ym", "median_deposit"]
    ].copy()

    merged = jeonse.merge(
        trade_agg[["gu_name", "ym", "median_price"]],
        on=["gu_name", "ym"],
        how="inner",
    )

    merged["jeonse_ratio"] = (
        merged["median_deposit"] / merged["median_price"] * 100
    ).round(1)

    return merged[["gu_name", "ym", "median_deposit", "median_price", "jeonse_ratio"]]


# --- v2 파생지표 ---


def calc_period_change(
    agg_df: pd.DataFrame, value_col: str = "median_price"
) -> pd.DataFrame:
    """구별 기간 상승률(%)을 계산한다. 시작월 vs 마지막월 비교."""
    if agg_df.empty:
        return pd.DataFrame(columns=["gu_name", "change_pct"])

    results = []
    for gu, group in agg_df.groupby("gu_name"):
        sorted_g = group.sort_values("ym")
        valid = sorted_g[value_col].dropna()
        if len(valid) < 2:
            continue
        first, last = valid.iloc[0], valid.iloc[-1]
        if first and first > 0:
            pct = round((last - first) / first * 100, 1)
        else:
            pct = 0.0
        results.append({"gu_name": gu, "change_pct": pct})

    if not results:
        return pd.DataFrame(columns=["gu_name", "change_pct"])
    return pd.DataFrame(results).sort_values("change_pct", ascending=False)


def calc_recent_momentum(
    agg_df: pd.DataFrame, value_col: str = "median_price", months: int = 3
) -> pd.DataFrame:
    """최근 N개월 상승률(%)을 계산한다."""
    if agg_df.empty:
        return pd.DataFrame(columns=["gu_name", "momentum_pct"])

    recent_yms = sorted(agg_df["ym"].unique())[-months:]
    recent = agg_df[agg_df["ym"].isin(recent_yms)]
    return calc_period_change(recent, value_col).rename(
        columns={"change_pct": "momentum_pct"}
    )


def calc_relative_premium(
    agg_df: pd.DataFrame, value_col: str = "median_price_per_sqm"
) -> pd.DataFrame:
    """서울 평균 대비 구별 프리미엄(%)을 계산한다.

    최신 월 기준으로 각 구의 값이 서울 전체 평균보다 몇 % 높거나 낮은지 반환.
    """
    if agg_df.empty:
        return pd.DataFrame(columns=["gu_name", "premium_pct"])

    latest_ym = agg_df["ym"].max()
    latest = agg_df[agg_df["ym"] == latest_ym]

    seoul_avg = latest[value_col].mean()
    if pd.isna(seoul_avg) or seoul_avg == 0:
        return pd.DataFrame(columns=["gu_name", "premium_pct"])

    result = latest[["gu_name", value_col]].copy()
    result["premium_pct"] = ((result[value_col] - seoul_avg) / seoul_avg * 100).round(1)
    return result[["gu_name", "premium_pct"]].sort_values("premium_pct", ascending=False)


def calc_volatility(
    agg_df: pd.DataFrame, value_col: str = "median_price"
) -> pd.DataFrame:
    """구별 월간 변화율의 표준편차(변동성)를 계산한다."""
    if agg_df.empty:
        return pd.DataFrame(columns=["gu_name", "volatility"])

    results = []
    for gu, group in agg_df.groupby("gu_name"):
        sorted_g = group.sort_values("ym")
        pct_changes = sorted_g[value_col].pct_change().dropna()
        std_val = pct_changes.std()
        vol = round(std_val * 100, 2) if (len(pct_changes) > 1 and not pd.isna(std_val)) else 0.0
        results.append({"gu_name": gu, "volatility": vol})

    return pd.DataFrame(results).sort_values("volatility", ascending=False)


def get_dong_gap_summary(df: pd.DataFrame) -> pd.DataFrame:
    """구 내 동별 중앙가 격차를 계산한다.

    Returns:
        gu_name, top_dong, top_price, bottom_dong, bottom_price, gap 컬럼.
    """
    if df.empty:
        return pd.DataFrame()

    dong_median = (
        df.groupby(["gu_name", "dong"])
        .agg(median_price=("price", "median"))
        .reset_index()
    )

    results = []
    for gu, group in dong_median.groupby("gu_name"):
        if len(group) < 2:
            continue
        top = group.loc[group["median_price"].idxmax()]
        bottom = group.loc[group["median_price"].idxmin()]
        results.append({
            "gu_name": gu,
            "top_dong": top["dong"],
            "top_price": int(top["median_price"]),
            "bottom_dong": bottom["dong"],
            "bottom_price": int(bottom["median_price"]),
            "gap": int(top["median_price"] - bottom["median_price"]),
        })

    if not results:
        return pd.DataFrame(columns=["gu_name", "top_dong", "top_price", "bottom_dong", "bottom_price", "gap"])
    return pd.DataFrame(results).sort_values("gap", ascending=False)


def generate_insight_text(
    gu_name: str,
    change_pct: float,
    momentum_pct: float,
    premium_pct: float,
    volatility: float,
) -> str:
    """KPI 값들을 기반으로 인사이트 문장을 생성한다."""
    parts = []

    # 상승/하락 판단
    if change_pct > 5:
        parts.append(f"{gu_name}은(는) 조회 기간 동안 {change_pct:+.1f}% 상승하며 강세를 보였습니다.")
    elif change_pct < -5:
        parts.append(f"{gu_name}은(는) 조회 기간 동안 {change_pct:+.1f}% 하락하며 약세를 보였습니다.")
    else:
        parts.append(f"{gu_name}은(는) 조회 기간 동안 {change_pct:+.1f}%로 보합세입니다.")

    # 모멘텀
    if momentum_pct > 3:
        parts.append(f"최근 3개월 모멘텀({momentum_pct:+.1f}%)이 강해 단기 상승 흐름이 이어지고 있습니다.")
    elif momentum_pct < -3:
        parts.append(f"최근 3개월 모멘텀({momentum_pct:+.1f}%)이 약해 단기 조정 가능성이 있습니다.")

    # 프리미엄
    if premium_pct > 20:
        parts.append(f"서울 평균 대비 {premium_pct:+.1f}% 프리미엄으로 고가 지역에 해당합니다.")
    elif premium_pct < -20:
        parts.append(f"서울 평균 대비 {premium_pct:+.1f}%로 상대적 저평가 구간입니다.")

    # 변동성
    if volatility > 5:
        parts.append(f"변동성({volatility:.1f}%)이 높아 가격 변동 리스크에 유의해야 합니다.")

    return " ".join(parts)


# --- 미활용 데이터 분석 ---


def calc_rent_escalation(rent_df: pd.DataFrame) -> pd.DataFrame:
    """갱신 계약의 보증금 인상률을 구별로 계산한다.

    prev_deposit > 0인 건만 대상 (갱신 계약).
    Returns:
        gu_name, avg_escalation_pct, median_escalation_pct, count 컬럼.
    """
    if rent_df.empty:
        return pd.DataFrame(columns=["gu_name", "avg_escalation_pct", "median_escalation_pct", "count"])

    df = rent_df.copy()
    if "prev_deposit" not in df.columns:
        return pd.DataFrame(columns=["gu_name", "avg_escalation_pct", "median_escalation_pct", "count"])

    df["prev_deposit"] = pd.to_numeric(df["prev_deposit"].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    renewal = df[(df["prev_deposit"] > 0) & (df["deposit"] > 0)].copy()
    if renewal.empty:
        return pd.DataFrame(columns=["gu_name", "avg_escalation_pct", "median_escalation_pct", "count"])

    renewal["escalation_pct"] = ((renewal["deposit"] - renewal["prev_deposit"]) / renewal["prev_deposit"] * 100).round(1)

    result = (
        renewal.groupby("gu_name")["escalation_pct"]
        .agg(avg_escalation_pct="mean", median_escalation_pct="median", count="count")
        .reset_index()
    )
    result["avg_escalation_pct"] = result["avg_escalation_pct"].round(1)
    result["median_escalation_pct"] = result["median_escalation_pct"].round(1)
    return result.sort_values("median_escalation_pct", ascending=False)


def calc_contract_type_ratio(rent_df: pd.DataFrame) -> pd.DataFrame:
    """구별 신규/갱신 계약 비율을 계산한다.

    Returns:
        gu_name, new_count, renewal_count, total, renewal_pct 컬럼.
    """
    if rent_df.empty or "contract_type" not in rent_df.columns:
        return pd.DataFrame(columns=["gu_name", "new_count", "renewal_count", "total", "renewal_pct"])

    df = rent_df.copy()
    df["contract_type"] = df["contract_type"].astype(str).str.strip()

    # 신규/갱신 구분
    df["ct_category"] = df["contract_type"].apply(
        lambda x: "갱신" if "갱신" in x else ("신규" if "신규" in x else "기타")
    )
    df = df[df["ct_category"].isin(["신규", "갱신"])]

    if df.empty:
        return pd.DataFrame(columns=["gu_name", "new_count", "renewal_count", "total", "renewal_pct"])

    pivot = df.groupby(["gu_name", "ct_category"]).size().unstack(fill_value=0).reset_index()
    pivot.columns.name = None

    result = pd.DataFrame()
    result["gu_name"] = pivot["gu_name"]
    result["new_count"] = pivot.get("신규", 0)
    result["renewal_count"] = pivot.get("갱신", 0)
    result["total"] = result["new_count"] + result["renewal_count"]
    result["renewal_pct"] = (result["renewal_count"] / result["total"] * 100).round(1)
    return result.sort_values("renewal_pct", ascending=False)


def calc_age_premium(trade_df: pd.DataFrame) -> pd.DataFrame:
    """연식별(신축/준신축/중축/구축) 가격 프리미엄을 계산한다.

    Returns:
        age_category, median_price, median_sqm_price, premium_pct 컬럼.
    """
    from datetime import datetime
    if trade_df.empty or "build_year" not in trade_df.columns:
        return pd.DataFrame(columns=["age_category", "median_price", "median_sqm_price", "premium_pct"])

    df = trade_df.dropna(subset=["build_year", "price_per_sqm"]).copy()
    cur = datetime.today().year

    def _categorize(by):
        if by >= cur - 5:
            return "신축"
        elif by >= cur - 10:
            return "준신축"
        elif by >= cur - 20:
            return "중축"
        else:
            return "구축"

    df["age_category"] = df["build_year"].apply(_categorize)
    overall_median = df["price_per_sqm"].median()

    result = (
        df.groupby("age_category")
        .agg(median_price=("price", "median"), median_sqm_price=("price_per_sqm", "median"), count=("price", "count"))
        .reset_index()
    )
    result["premium_pct"] = ((result["median_sqm_price"] - overall_median) / overall_median * 100).round(1)
    result["median_price"] = result["median_price"].round(0)
    result["median_sqm_price"] = result["median_sqm_price"].round(0)

    order = {"신축": 0, "준신축": 1, "중축": 2, "구축": 3}
    result["_order"] = result["age_category"].map(order)
    return result.sort_values("_order").drop(columns="_order")


def calc_direct_trade_ratio(trade_df: pd.DataFrame) -> pd.DataFrame:
    """구별 직거래/중개거래 비율을 계산한다.

    Returns:
        gu_name, direct_count, broker_count, total, direct_pct 컬럼.
    """
    if trade_df.empty or "trade_type" not in trade_df.columns:
        return pd.DataFrame(columns=["gu_name", "direct_count", "broker_count", "total", "direct_pct"])

    df = trade_df.copy()
    df["trade_type"] = df["trade_type"].astype(str).str.strip()

    df["tt_category"] = df["trade_type"].apply(
        lambda x: "직거래" if "직거래" in x else "중개거래"
    )

    pivot = df.groupby(["gu_name", "tt_category"]).size().unstack(fill_value=0).reset_index()
    pivot.columns.name = None

    result = pd.DataFrame()
    result["gu_name"] = pivot["gu_name"]
    result["direct_count"] = pivot.get("직거래", 0)
    result["broker_count"] = pivot.get("중개거래", 0)
    result["total"] = result["direct_count"] + result["broker_count"]
    result["direct_pct"] = (result["direct_count"] / result["total"] * 100).round(1)
    return result.sort_values("direct_pct", ascending=False)


# --- 심층 분석 함수 ---


def decompose_price_series(history: pd.DataFrame, period: int = 12) -> dict | None:
    """월별 중위가 시계열을 STL 분해한다.

    Args:
        history: get_apt_price_history() 결과 (ym, median_price 컬럼 필요)
        period: 계절성 주기 (12 = 연간)

    Returns:
        {"observed", "trend", "seasonal", "resid"} 각각 pd.Series (index=ym),
        또는 데이터 부족 시 None.
    """
    if history is None or history.empty or len(history) < period + 2:
        return None

    try:
        from statsmodels.tsa.seasonal import STL

        series = history.set_index("ym")["median_price"].copy()
        series.index = pd.PeriodIndex(series.index, freq="M")
        series = series.asfreq("M")
        series = series.interpolate(method="linear")

        if series.isna().sum() > len(series) * 0.3:
            return None

        stl = STL(series, period=period, robust=True)
        result = stl.fit()

        return {
            "observed": result.observed,
            "trend": result.trend,
            "seasonal": result.seasonal,
            "resid": result.resid,
        }
    except Exception:
        return None


def calc_rolling_volatility(history: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
    """월별 중위가의 롤링 변동성(변화율 표준편차)을 계산한다.

    Returns:
        ym, vol_3m, vol_6m 등 컬럼.
    """
    if windows is None:
        windows = [3, 6]
    if history is None or history.empty or len(history) < max(windows) + 1:
        return pd.DataFrame()

    df = history[["ym", "median_price"]].copy().sort_values("ym")
    df["pct_change"] = df["median_price"].pct_change() * 100

    for w in windows:
        df[f"vol_{w}m"] = df["pct_change"].rolling(w).std().round(2)

    return df.dropna(subset=[f"vol_{windows[0]}m"])


def calc_max_drawdown(history: pd.DataFrame) -> dict:
    """월별 중위가에서 최대 낙폭(MDD)을 계산한다.

    Returns:
        {"mdd_pct": float, "peak_ym": str, "trough_ym": str,
         "drawdown_series": pd.DataFrame(ym, drawdown_pct)}
    """
    if history is None or history.empty or len(history) < 2:
        return {"mdd_pct": 0, "peak_ym": "-", "trough_ym": "-", "drawdown_series": pd.DataFrame()}

    df = history[["ym", "median_price"]].copy().sort_values("ym")
    df["running_max"] = df["median_price"].cummax()
    df["drawdown_pct"] = ((df["median_price"] - df["running_max"]) / df["running_max"] * 100).round(2)

    mdd_idx = df["drawdown_pct"].idxmin()
    mdd_pct = df.loc[mdd_idx, "drawdown_pct"]
    trough_ym = df.loc[mdd_idx, "ym"]

    # 해당 낙폭의 고점 찾기
    peak_idx = df.loc[:mdd_idx, "median_price"].idxmax()
    peak_ym = df.loc[peak_idx, "ym"]

    return {
        "mdd_pct": round(mdd_pct, 1),
        "peak_ym": peak_ym,
        "trough_ym": trough_ym,
        "drawdown_series": df[["ym", "drawdown_pct"]],
    }


def calc_liquidity_score(df_apt: pd.DataFrame, df_dong: pd.DataFrame) -> dict:
    """단지의 유동성 점수를 계산한다 (동 평균 대비 거래 빈도).

    Returns:
        {"apt_monthly_avg": float, "dong_monthly_avg": float,
         "liquidity_ratio": float, "monthly_counts": pd.DataFrame}
    """
    if df_apt.empty:
        return {"apt_monthly_avg": 0, "dong_monthly_avg": 0, "liquidity_ratio": 0,
                "monthly_counts": pd.DataFrame()}

    apt_monthly = df_apt.groupby("ym").size().reset_index(name="apt_count")
    dong_monthly = df_dong.groupby("ym").size().reset_index(name="dong_count")

    merged = apt_monthly.merge(dong_monthly, on="ym", how="outer").fillna(0)
    apt_avg = merged["apt_count"].mean()
    dong_avg = merged["dong_count"].mean()
    ratio = round(apt_avg / dong_avg, 2) if dong_avg > 0 else 0

    return {
        "apt_monthly_avg": round(apt_avg, 1),
        "dong_monthly_avg": round(dong_avg, 1),
        "liquidity_ratio": ratio,
        "monthly_counts": merged,
    }


def find_comparable_complexes(
    df_gu: pd.DataFrame,
    target_apt: str,
    target_build_year: int,
    target_area: float,
    max_results: int = 10,
) -> pd.DataFrame:
    """비교 단지를 자동 선별한다.

    조건: 같은 구, 건축연도 +-5년, 비슷한 면적대, 거래 10건+.
    Returns:
        apt_name, dong, build_year, median_price, median_sqm, trade_count,
        change_pct, is_target 컬럼.
    """
    if df_gu.empty:
        return pd.DataFrame()

    # 면적 범위 (타겟 +-15m2)
    area_low = target_area - 15
    area_high = target_area + 15

    results = []
    for (dong, apt), group in df_gu.groupby(["dong", "apt_name"]):
        # 면적 필터
        area_filtered = group[(group["area"] >= area_low) & (group["area"] <= area_high)]
        if len(area_filtered) < 5:
            continue

        by = area_filtered["build_year"].median()
        if pd.isna(by) or abs(by - target_build_year) > 5:
            if apt != target_apt:
                continue

        history = area_filtered.groupby("ym")["price"].median().sort_index()
        median_price = area_filtered["price"].median()
        median_sqm = area_filtered["price_per_sqm"].median()
        trade_count = len(area_filtered)

        change_pct = 0.0
        if len(history) >= 2:
            change_pct = round((history.iloc[-1] - history.iloc[0]) / history.iloc[0] * 100, 1)

        results.append({
            "apt_name": apt,
            "dong": dong,
            "build_year": int(by) if not pd.isna(by) else 0,
            "median_price": int(median_price),
            "median_sqm": round(median_sqm, 1),
            "trade_count": trade_count,
            "change_pct": change_pct,
            "is_target": apt == target_apt,
        })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results).sort_values("median_sqm", ascending=False)
    # 타겟은 항상 포함, 나머지는 상위 max_results
    target_rows = df[df["is_target"]]
    others = df[~df["is_target"]].head(max_results)
    return pd.concat([target_rows, others], ignore_index=True)


def calc_investment_score(
    change_6m: float,
    jeonse_ratio: float,
    liquidity_ratio: float,
    volatility: float,
    gap_ratio: float,
    comparable_rank_pct: float,
) -> dict:
    """6축 투자 스코어카드를 계산한다.

    각 축 0~100 점수.
    Returns:
        {"scores": dict, "total": float, "strengths": list, "weaknesses": list}
    """
    def _clamp(v):
        return max(0, min(100, v))

    # 1. 가격 추세: 상승률 → 점수 (6개월 +10%=100, -10%=0)
    trend_score = _clamp(50 + change_6m * 5)

    # 2. 전세가율: 높을수록 좋음 (80%=100, 40%=0)
    jeonse_score = _clamp((jeonse_ratio - 40) / 40 * 100) if jeonse_ratio > 0 else 50

    # 3. 유동성: 동 평균 대비 배수 (2배=100, 0=0)
    liquidity_score = _clamp(liquidity_ratio * 50)

    # 4. 안정성: 변동성 낮을수록 좋음 (0%=100, 10%=0)
    stability_score = _clamp(100 - volatility * 10)

    # 5. 갭 안전성: 갭 비율 작을수록 좋음 (0%=100, 50%=0)
    gap_score = _clamp(100 - gap_ratio * 2)

    # 6. 비교 우위: 비교 단지 내 순위 백분위 (상위=100)
    comp_score = _clamp(comparable_rank_pct)

    scores = {
        "가격 추세": round(trend_score),
        "전세가율": round(jeonse_score),
        "유동성": round(liquidity_score),
        "안정성": round(stability_score),
        "갭 안전성": round(gap_score),
        "비교 우위": round(comp_score),
    }
    total = round(sum(scores.values()) / len(scores))

    strengths = [k for k, v in scores.items() if v >= 70]
    weaknesses = [k for k, v in scores.items() if v < 40]

    return {"scores": scores, "total": total, "strengths": strengths, "weaknesses": weaknesses}

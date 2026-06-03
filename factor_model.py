"""아파트 알파/베타 팩터 모델.

서울 아파트 가격 변동을 5개 시스템 팩터(베타)와 단지 고유 성과(알파)로 분해한다.

모델:
    R_단지(t) = alpha + beta1*R_서울(t) + beta2*R_구(t) + beta3*R_면적대(t)
                + beta4*R_연식(t) + beta5*Delta_전세가율(t) + epsilon(t)
"""

import pandas as pd
import numpy as np
from datetime import datetime


# ---------------------------------------------------------------------------
# 1. 팩터 수익률 구축
# ---------------------------------------------------------------------------

def _monthly_return(series: pd.Series) -> pd.Series:
    """월별 수익률(%) 계산. NaN은 0, 극단값은 +-30%로 윈저화."""
    ret = series.pct_change() * 100
    ret = ret.fillna(0)
    ret = ret.clip(lower=-30, upper=30)  # 월간 30% 이상 변동은 노이즈
    return ret


def build_factor_returns(
    trade_df: pd.DataFrame,
    gu_name: str,
    area_category: str | None = None,
    age_category: str | None = None,
) -> pd.DataFrame:
    """월별 5개 팩터 수익률 테이블을 생성한다.

    Args:
        trade_df: clean_trade_data() 결과 (전체 서울 데이터 권장).
        gu_name: 분석 대상 구.
        area_category: 면적대 카테고리 (None이면 전체).
        age_category: 연식 카테고리 ("신축"/"준신축"/"중축"/"구축", None이면 전체).

    Returns:
        DataFrame(ym, r_seoul, r_gu, r_area, r_age, d_jeonse)
        각 값은 월간 수익률(%).
    """
    if trade_df.empty:
        return pd.DataFrame()

    # m2당 단가 기준으로 팩터 계산 (면적 혼합 영향 제거)
    price_col = "price_per_sqm" if "price_per_sqm" in trade_df.columns else "price"

    # --- Factor 1: 서울 시장 수익률 (해당 구 제외 → 직교화) ---
    df_ex_gu = trade_df[trade_df["gu_name"] != gu_name]
    seoul_monthly = (
        df_ex_gu.groupby("ym")[price_col]
        .median()
        .sort_index()
    )
    r_seoul = _monthly_return(seoul_monthly).rename("r_seoul")

    # --- Factor 2: 구 초과수익률 ---
    gu_monthly = (
        trade_df[trade_df["gu_name"] == gu_name]
        .groupby("ym")[price_col]
        .median()
        .sort_index()
    )
    r_gu_raw = _monthly_return(gu_monthly)
    r_gu = (r_gu_raw - r_seoul).rename("r_gu")

    # --- Factor 3: 면적대 초과수익률 (해당 구 제외) ---
    if area_category and "area_category" in trade_df.columns:
        area_data = df_ex_gu[df_ex_gu["area_category"] == area_category]
        if not area_data.empty:
            area_monthly = area_data.groupby("ym")[price_col].median().sort_index()
            r_area = (_monthly_return(area_monthly) - r_seoul).rename("r_area")
        else:
            r_area = pd.Series(0, index=r_seoul.index, name="r_area")
    else:
        r_area = pd.Series(0, index=r_seoul.index, name="r_area")

    # --- Factor 4: 연식 코호트 초과수익률 (해당 구 제외) ---
    if age_category and "build_year" in trade_df.columns:
        cur = datetime.today().year
        age_ranges = {
            "신축": (cur - 5, cur + 1),
            "준신축": (cur - 10, cur - 5),
            "중축": (cur - 20, cur - 10),
            "구축": (0, cur - 20),
        }
        if age_category in age_ranges:
            lo, hi = age_ranges[age_category]
            age_data = df_ex_gu[df_ex_gu["build_year"].between(lo, hi - 1)]
            if not age_data.empty:
                age_monthly = age_data.groupby("ym")[price_col].median().sort_index()
                r_age = (_monthly_return(age_monthly) - r_seoul).rename("r_age")
            else:
                r_age = pd.Series(0, index=r_seoul.index, name="r_age")
        else:
            r_age = pd.Series(0, index=r_seoul.index, name="r_age")
    else:
        r_age = pd.Series(0, index=r_seoul.index, name="r_age")

    # --- Factor 5: 전세가율 변화 ---
    # 전세 데이터가 없으면 0으로 채움 (나중에 외부에서 주입 가능)
    d_jeonse = pd.Series(0, index=r_seoul.index, name="d_jeonse")

    # 합치기
    factors = pd.concat([r_seoul, r_gu, r_area, r_age, d_jeonse], axis=1)
    factors.index.name = "ym"
    factors = factors.reset_index()
    factors = factors.fillna(0)

    return factors


def inject_jeonse_factor(
    factor_df: pd.DataFrame,
    jeonse_ratio_df: pd.DataFrame,
    gu_name: str,
) -> pd.DataFrame:
    """전세가율 변화를 팩터 테이블에 주입한다.

    Args:
        factor_df: build_factor_returns() 결과.
        jeonse_ratio_df: calc_jeonse_ratio() 결과 (gu_name, ym, jeonse_ratio).
        gu_name: 대상 구.
    """
    if factor_df.empty or jeonse_ratio_df.empty:
        return factor_df

    gu_jeonse = (
        jeonse_ratio_df[jeonse_ratio_df["gu_name"] == gu_name]
        .sort_values("ym")
        .set_index("ym")["jeonse_ratio"]
    )

    if gu_jeonse.empty:
        return factor_df

    d_jeonse = gu_jeonse.pct_change().fillna(0) * 100
    d_jeonse.name = "d_jeonse"

    factor_df = factor_df.set_index("ym")
    factor_df["d_jeonse"] = d_jeonse
    factor_df["d_jeonse"] = factor_df["d_jeonse"].fillna(0)
    return factor_df.reset_index()


# ---------------------------------------------------------------------------
# 2. 알파/베타 회귀
# ---------------------------------------------------------------------------

FACTOR_COLS = ["r_seoul", "r_gu", "r_area", "r_age", "d_jeonse"]
FACTOR_LABELS = {
    "r_seoul": "서울 시장 (타 구)",
    "r_gu": "구 고유 효과",
    "r_area": "면적대 효과",
    "r_age": "연식 효과",
    "d_jeonse": "전세시장 압력",
}


def calc_alpha_beta(
    complex_history: pd.DataFrame,
    factor_returns: pd.DataFrame,
    window: int = 12,
    min_periods: int = 8,
) -> dict | None:
    """롤링 OLS로 시변 알파/베타를 추출한다.

    Args:
        complex_history: get_apt_price_history() 결과 (ym, median_price).
        factor_returns: build_factor_returns() 결과.
        window: 롤링 윈도우 (월).
        min_periods: 최소 데이터 포인트.

    Returns:
        {
            "alpha_series": DataFrame(ym, alpha),
            "beta_series": DataFrame(ym, beta_seoul, beta_gu, ...),
            "latest_alpha": float,
            "latest_betas": dict,
            "r_squared": float,
            "factor_contribution": dict,  # 각 팩터가 기간 수익률의 몇 %p 기여
        }
        또는 데이터 부족 시 None.
    """
    if complex_history is None or complex_history.empty or len(complex_history) < min_periods:
        return None
    if factor_returns.empty:
        return None

    try:
        import statsmodels.api as sm
    except ImportError:
        return None

    # 단지 수익률 계산 (m2당 단가 기준, 없으면 총가 fallback)
    sqm_col = "median_price_per_sqm" if "median_price_per_sqm" in complex_history.columns else "median_price"
    ch = complex_history[["ym", sqm_col]].copy().sort_values("ym")
    ch["r_complex"] = _monthly_return(ch[sqm_col])
    ch = ch[ch["r_complex"] != 0]  # 첫 행 제거

    # 팩터와 merge
    merged = ch.merge(factor_returns, on="ym", how="inner")
    if len(merged) < min_periods:
        return None

    # 사용 가능한 팩터만 선택 (분산이 0인 팩터 제외)
    available_factors = []
    for f in FACTOR_COLS:
        if f in merged.columns and merged[f].std() > 0.001:
            available_factors.append(f)

    if not available_factors:
        return None

    y = merged["r_complex"].values
    X = merged[available_factors].values
    X_const = sm.add_constant(X)

    # --- 전체 기간 OLS ---
    try:
        model = sm.OLS(y, X_const).fit()
        r_squared = round(model.rsquared, 3)
        full_alpha = round(model.params[0], 3)
        full_betas = {f: round(model.params[i + 1], 3) for i, f in enumerate(available_factors)}
    except Exception:
        r_squared = 0
        full_alpha = 0
        full_betas = {f: 0 for f in available_factors}

    # --- 팩터별 기여도: 직접 벤치마크 차감 방식 ---
    # OLS 베타 * 팩터합 방식은 R²가 낮을 때 불안정.
    # 대신: 단지 누적수익률에서 각 벤치마크 누적수익률을 순차 차감
    total_complex = merged["r_complex"].sum()
    factor_contribution = {}

    # 각 팩터의 누적 수익률 = 벤치마크가 얼마나 움직였는지
    remaining = total_complex
    for f in available_factors:
        factor_total = merged[f].sum()
        # 팩터 기여 = 해당 벤치마크의 누적 변화
        # r_seoul: 서울 시장이 움직인 만큼
        # r_gu: 구가 서울 대비 추가로 움직인 만큼
        # r_area: 면적대가 추가로 움직인 만큼 (이미 직교화됨)
        if f == "r_seoul":
            # 서울 시장 기여 = 서울 시장 수익률 합 (서울이 움직인 만큼은 베타)
            contrib = round(factor_total, 1)
        elif f in ("r_gu", "r_area", "r_age"):
            # 초과수익률 팩터: 해당 세그먼트가 서울 대비 추가로 움직인 만큼
            contrib = round(factor_total, 1)
        else:
            # 전세가율 등 기타 팩터
            contrib = round(factor_total * full_betas.get(f, 0), 1)
        factor_contribution[FACTOR_LABELS.get(f, f)] = contrib
        remaining -= contrib

    factor_contribution["알파 (고유 가치)"] = round(remaining, 1)

    # --- 롤링 알파/베타 ---
    alpha_list = []
    beta_list = []

    for end_idx in range(min_periods, len(merged) + 1):
        start_idx = max(0, end_idx - window)
        window_data = merged.iloc[start_idx:end_idx]

        if len(window_data) < min_periods:
            continue

        ym = window_data["ym"].iloc[-1]
        y_w = window_data["r_complex"].values
        X_w = sm.add_constant(window_data[available_factors].values)

        try:
            m = sm.OLS(y_w, X_w).fit()
            alpha_list.append({"ym": ym, "alpha": round(m.params[0], 3)})
            beta_row = {"ym": ym}
            for i, f in enumerate(available_factors):
                beta_row[f"beta_{f}"] = round(m.params[i + 1], 3)
            beta_list.append(beta_row)
        except Exception:
            continue

    alpha_series = pd.DataFrame(alpha_list) if alpha_list else pd.DataFrame(columns=["ym", "alpha"])
    beta_series = pd.DataFrame(beta_list) if beta_list else pd.DataFrame()

    return {
        "alpha_series": alpha_series,
        "beta_series": beta_series,
        "latest_alpha": alpha_list[-1]["alpha"] if alpha_list else 0,
        "latest_betas": full_betas,
        "r_squared": r_squared,
        "factor_contribution": factor_contribution,
        "available_factors": available_factors,
    }


# ---------------------------------------------------------------------------
# 3. 수익률 분해
# ---------------------------------------------------------------------------

def decompose_returns(
    complex_history: pd.DataFrame,
    factor_returns: pd.DataFrame,
    betas: dict,
    available_factors: list[str],
    alpha_monthly: float = 0.0,
) -> pd.DataFrame:
    """월별 수익률을 팩터별 기여분으로 분해한다.

    Args:
        alpha_monthly: OLS intercept (월평균 알파 %p).

    Returns:
        DataFrame(ym, actual_return, {factor}_contrib, ..., 알파, 잔차)
    """
    if complex_history is None or complex_history.empty or factor_returns.empty:
        return pd.DataFrame()

    sqm_col = "median_price_per_sqm" if "median_price_per_sqm" in complex_history.columns else "median_price"
    ch = complex_history[["ym", sqm_col]].copy().sort_values("ym")
    ch["actual_return"] = _monthly_return(ch[sqm_col])

    merged = ch.merge(factor_returns, on="ym", how="inner").dropna(subset=["actual_return"])
    if merged.empty:
        return pd.DataFrame()

    result = merged[["ym", "actual_return"]].copy()

    # 직접 차감 방식: 서울 수익률 → 구 초과 → 면적대 초과 → 연식 초과 → 나머지 = 알파
    total_factors = pd.Series(0, index=result.index, dtype=float)
    for f in available_factors:
        col_name = FACTOR_LABELS.get(f, f)
        if f in ("r_seoul", "r_gu", "r_area", "r_age"):
            result[col_name] = merged[f].round(2)
        else:
            beta = betas.get(f, 0)
            result[col_name] = (merged[f] * beta).round(2)
        total_factors += result[col_name]

    # 알파 = 실제 수익률 - 모든 벤치마크 합 (월별)
    result["알파 (고유)"] = (result["actual_return"] - total_factors).round(2)

    return result

"""아파트 스크리닝 엔진.

조건에 맞는 단지들을 다차원 스코어링하여 랭킹한다.
주식 퀀트의 팩터 스크리닝과 동일한 개념.
"""

import pandas as pd
import numpy as np
from datetime import datetime


def screen_complexes(
    trade_df: pd.DataFrame,
    rent_df: pd.DataFrame = None,
    target_area: int = 85,
    area_tolerance: int = 5,
    min_trades: int = 5,
    months_momentum: int = 6,
) -> pd.DataFrame:
    """조건에 맞는 단지를 스크리닝하고 다차원 스코어를 계산한다.

    Args:
        trade_df: clean_trade_data() + add_area_category() 결과.
        rent_df: clean_rent_data() 결과 (없으면 전세 관련 스코어 0).
        target_area: 타겟 전용면적 (m2).
        area_tolerance: 면적 허용 오차 (+-m2).
        min_trades: 최소 거래건수 (이하 제외).
        months_momentum: 모멘텀 계산 기간 (월).

    Returns:
        DataFrame with columns:
            gu_name, dong, apt_name, build_year, median_sqm, total_trades,
            momentum_pct, value_rank_pct, alpha_pct, liquidity_ratio,
            jeonse_ratio, volatility,
            score_momentum, score_value, score_alpha, score_liquidity, score_safety,
            score_total
    """
    if trade_df.empty:
        return pd.DataFrame()

    # 면적 필터
    area_lo = target_area - area_tolerance
    area_hi = target_area + area_tolerance
    df = trade_df[(trade_df["area"] >= area_lo) & (trade_df["area"] <= area_hi)].copy()

    if df.empty:
        return pd.DataFrame()

    results = []
    all_yms = sorted(df["ym"].unique())

    # 모멘텀 기간 계산용
    if len(all_yms) >= months_momentum:
        recent_yms = all_yms[-months_momentum:]
        older_yms = all_yms[:-months_momentum]
    else:
        recent_yms = all_yms
        older_yms = []

    for (gu, dong, apt), group in df.groupby(["gu_name", "dong", "apt_name"]):
        if len(group) < min_trades:
            continue

        monthly = group.groupby("ym")["price_per_sqm"].median().sort_index()
        if len(monthly) < 3:
            continue

        # 기본 정보
        build_year = int(group["build_year"].median()) if group["build_year"].notna().any() else 0
        median_sqm = round(group["price_per_sqm"].median(), 1)
        median_price = int(group["price"].median())
        total_trades = len(group)

        # --- Momentum ---
        recent_data = group[group["ym"].isin(recent_yms)]
        older_data = group[group["ym"].isin(older_yms)] if older_yms else pd.DataFrame()

        if not recent_data.empty and not older_data.empty:
            recent_sqm = recent_data["price_per_sqm"].median()
            older_sqm = older_data["price_per_sqm"].median()
            momentum_pct = round((recent_sqm - older_sqm) / older_sqm * 100, 1) if older_sqm > 0 else 0
        elif len(monthly) >= 2:
            momentum_pct = round((monthly.iloc[-1] - monthly.iloc[0]) / monthly.iloc[0] * 100, 1) if monthly.iloc[0] > 0 else 0
        else:
            momentum_pct = 0

        # --- Volatility ---
        pct_changes = monthly.pct_change().dropna()
        volatility = round(pct_changes.std() * 100, 2) if len(pct_changes) > 1 else 0

        # --- Liquidity (월평균 거래건수) ---
        months_with_data = group["ym"].nunique()
        monthly_avg_trades = round(total_trades / max(months_with_data, 1), 1)

        # --- Alpha (간이): 같은 구 동일 면적 대비 초과 수익률 ---
        gu_data = df[df["gu_name"] == gu]
        gu_monthly = gu_data.groupby("ym")["price_per_sqm"].median().sort_index()
        if len(gu_monthly) >= 2 and len(monthly) >= 2:
            # 공통 기간만
            common_yms = monthly.index.intersection(gu_monthly.index)
            if len(common_yms) >= 2:
                apt_return = (monthly[common_yms].iloc[-1] - monthly[common_yms].iloc[0]) / monthly[common_yms].iloc[0] * 100
                gu_return = (gu_monthly[common_yms].iloc[-1] - gu_monthly[common_yms].iloc[0]) / gu_monthly[common_yms].iloc[0] * 100
                alpha_pct = round(apt_return - gu_return, 1)
            else:
                alpha_pct = 0
        else:
            alpha_pct = 0

        results.append({
            "gu_name": gu,
            "dong": dong,
            "apt_name": apt,
            "build_year": build_year,
            "median_sqm": median_sqm,
            "median_price": median_price,
            "total_trades": total_trades,
            "momentum_pct": momentum_pct,
            "volatility": volatility,
            "monthly_trades": monthly_avg_trades,
            "alpha_pct": alpha_pct,
        })

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    # --- Jeonse ratio (전세가율) ---
    result_df["jeonse_ratio"] = 0.0
    if rent_df is not None and not rent_df.empty:
        jeonse = rent_df[
            (rent_df["area"] >= area_lo) & (rent_df["area"] <= area_hi) &
            (rent_df["rent_type"] == "전세")
        ]
        if not jeonse.empty:
            jeonse_by_apt = jeonse.groupby(["gu_name", "apt_name"])["deposit"].median()
            for idx, row in result_df.iterrows():
                key = (row["gu_name"], row["apt_name"])
                if key in jeonse_by_apt.index:
                    deposit = jeonse_by_apt[key]
                    result_df.at[idx, "jeonse_ratio"] = round(
                        deposit / row["median_price"] * 100, 1
                    ) if row["median_price"] > 0 else 0

    # --- 스코어링 (0~100) ---
    result_df = _calc_scores(result_df)

    return result_df.sort_values("score_total", ascending=False).reset_index(drop=True)


def _percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """시리즈를 0~100 백분위 점수로 변환."""
    if series.nunique() <= 1:
        return pd.Series(50, index=series.index)
    ranked = series.rank(pct=True) * 100
    if not higher_is_better:
        ranked = 100 - ranked
    return ranked.round(0)


def _calc_scores(df: pd.DataFrame) -> pd.DataFrame:
    """각 스코어를 계산하고 종합 점수를 산출한다."""
    df = df.copy()

    # Momentum Score: 상승률 높을수록 높은 점수
    df["score_momentum"] = _percentile_score(df["momentum_pct"], higher_is_better=True)

    # Value Score: m2당가 낮을수록 높은 점수 (상대적 저평가)
    # 구별로 정규화 (같은 구 내에서만 비교)
    df["score_value"] = 0
    for gu in df["gu_name"].unique():
        mask = df["gu_name"] == gu
        if mask.sum() > 1:
            df.loc[mask, "score_value"] = _percentile_score(
                df.loc[mask, "median_sqm"], higher_is_better=False
            )
        else:
            df.loc[mask, "score_value"] = 50

    # Alpha Score: 알파 높을수록 높은 점수
    df["score_alpha"] = _percentile_score(df["alpha_pct"], higher_is_better=True)

    # Liquidity Score: 거래 활발할수록 높은 점수
    df["score_liquidity"] = _percentile_score(df["monthly_trades"], higher_is_better=True)

    # Safety Score: 전세가율 높고 + 변동성 낮으면 높은 점수
    safety_raw = df["jeonse_ratio"] - df["volatility"] * 5
    df["score_safety"] = _percentile_score(safety_raw, higher_is_better=True)

    # 종합 점수 (가중 평균)
    weights = {
        "score_momentum": 0.30,
        "score_value": 0.20,
        "score_alpha": 0.20,
        "score_liquidity": 0.15,
        "score_safety": 0.15,
    }
    df["score_total"] = sum(
        df[col] * w for col, w in weights.items()
    ).round(0)

    return df

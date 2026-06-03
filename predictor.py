import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder


class AptPricePredictor:
    """서울 아파트 가격 예측 모델."""

    def __init__(self):
        self.model = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
        )
        self.gu_encoder = LabelEncoder()
        self.is_trained = False
        self.metrics = {}
        self.feature_names = []

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """학습/예측용 feature를 생성한다."""
        features = df[["area", "build_year", "floor", "gu_name", "year", "month"]].copy()
        features = features.dropna()

        # 건물 나이 계산
        features["building_age"] = features["year"] - features["build_year"]
        features = features.drop(columns=["build_year"])

        return features

    def train(self, df: pd.DataFrame) -> dict:
        """모델을 학습하고 성능 지표를 반환한다.

        Args:
            df: clean_trade_data를 거친 DataFrame.

        Returns:
            {"mae": float, "r2": float, "train_size": int, "test_size": int}
        """
        features = self.prepare_features(df)
        if features.empty or len(features) < 10:
            self.metrics = {"mae": 0, "r2": 0, "train_size": 0, "test_size": 0}
            return self.metrics

        target = df.loc[features.index, "price"]

        # 구 이름 인코딩
        features["gu_encoded"] = self.gu_encoder.fit_transform(features["gu_name"])
        X = features[["area", "floor", "building_age", "gu_encoded", "year", "month"]]
        y = target

        self.feature_names = list(X.columns)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        self.model.fit(X_train, y_train)
        self.is_trained = True

        y_pred = self.model.predict(X_test)
        self.metrics = {
            "mae": round(mean_absolute_error(y_test, y_pred), 0),
            "r2": round(r2_score(y_test, y_pred), 4),
            "train_size": len(X_train),
            "test_size": len(X_test),
        }
        return self.metrics

    def predict(
        self,
        area: float,
        floor: int,
        building_age: int,
        gu_name: str,
        year: int,
        month: int,
    ) -> float | None:
        """단일 조건으로 가격을 예측한다.

        Returns:
            예상 가격 (만원). 학습되지 않았거나 알 수 없는 구면 None.
        """
        if not self.is_trained:
            return None

        try:
            gu_encoded = self.gu_encoder.transform([gu_name])[0]
        except ValueError:
            return None

        X = pd.DataFrame(
            [[area, floor, building_age, gu_encoded, year, month]],
            columns=self.feature_names,
        )
        return round(self.model.predict(X)[0], 0)

    def get_feature_importance(self) -> pd.DataFrame:
        """feature 중요도를 반환한다."""
        if not self.is_trained:
            return pd.DataFrame()

        importance = pd.DataFrame(
            {
                "feature": self.feature_names,
                "importance": self.model.feature_importances_,
            }
        ).sort_values("importance", ascending=False)

        label_map = {
            "area": "전용면적",
            "floor": "층",
            "building_age": "건물나이",
            "gu_encoded": "구",
            "year": "거래년도",
            "month": "거래월",
        }
        importance["feature_kr"] = importance["feature"].map(label_map)
        return importance

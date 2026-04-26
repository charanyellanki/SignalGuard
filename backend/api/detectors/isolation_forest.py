"""Point-anomaly detector: scikit-learn IsolationForest wrapper.

Features (order matters — must match LSTM AE and training):
    battery_voltage, lock_events_count, signal_strength_dbm, temperature_c
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

FEATURE_ORDER = (
    "battery_voltage",
    "lock_events_count",
    "signal_strength_dbm",
    "temperature_c",
)


def vectorize(sample: dict) -> np.ndarray:
    return np.array([float(sample[f]) for f in FEATURE_ORDER], dtype=np.float32)


@dataclass
class IForestDetector:
    model: IsolationForest
    scaler: StandardScaler

    @classmethod
    def train(cls, x: np.ndarray, *, contamination: float = 0.02) -> "IForestDetector":
        scaler = StandardScaler().fit(x)
        model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=42,
            n_jobs=-1,
        ).fit(scaler.transform(x))
        return cls(model=model, scaler=scaler)

    def predict(self, sample: dict) -> tuple[bool, float]:
        """Returns ``(is_anomaly, score)``. Score is +ve for anomalies,
        magnitude ~ how far outside the decision boundary."""
        x = self.scaler.transform(vectorize(sample).reshape(1, -1))
        score = float(-self.model.decision_function(x)[0])
        is_anom = bool(self.model.predict(x)[0] == -1)
        return is_anom, score

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "scaler": self.scaler}, path)

    @classmethod
    def load(cls, path: Path) -> "IForestDetector":
        obj = joblib.load(path)
        return cls(model=obj["model"], scaler=obj["scaler"])

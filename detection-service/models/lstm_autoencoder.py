"""Sequence-anomaly detector: per-device LSTM autoencoder.

Takes a rolling window of the last ``WINDOW_SIZE`` samples per device,
encodes → decodes, flags when reconstruction error exceeds a learned
threshold (95th percentile of training errors).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .isolation_forest import FEATURE_ORDER, vectorize  # share feature order

WINDOW_SIZE = 10
N_FEATURES = len(FEATURE_ORDER)
HIDDEN_DIM = 16


class LSTMAutoencoder(nn.Module):
    def __init__(self, n_features: int = N_FEATURES, hidden_dim: int = HIDDEN_DIM):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.encoder = nn.LSTM(n_features, hidden_dim, batch_first=True)
        self.decoder = nn.LSTM(hidden_dim, hidden_dim, batch_first=True)
        self.output = nn.Linear(hidden_dim, n_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (h, _) = self.encoder(x)
        # Repeat latent across timesteps, decode back to feature space.
        repeated = h.squeeze(0).unsqueeze(1).repeat(1, x.size(1), 1)
        decoded, _ = self.decoder(repeated)
        return self.output(decoded)


@dataclass
class LSTMAutoencoderDetector:
    model: LSTMAutoencoder
    mean: np.ndarray
    std: np.ndarray
    threshold: float
    window_size: int = WINDOW_SIZE

    @classmethod
    def train(
        cls,
        windows: np.ndarray,
        *,
        epochs: int = 25,
        lr: float = 1e-3,
        batch_size: int = 128,
        threshold_pct: float = 99.0,
    ) -> "LSTMAutoencoderDetector":
        assert windows.ndim == 3 and windows.shape[1:] == (WINDOW_SIZE, N_FEATURES)

        mean = windows.reshape(-1, N_FEATURES).mean(axis=0)
        std = windows.reshape(-1, N_FEATURES).std(axis=0) + 1e-6
        norm = (windows - mean) / std

        device = torch.device("cpu")
        model = LSTMAutoencoder().to(device)
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        loss_fn = nn.MSELoss()

        x = torch.tensor(norm, dtype=torch.float32, device=device)
        n = x.size(0)
        model.train()
        for _ in range(epochs):
            idx = torch.randperm(n)
            for start in range(0, n, batch_size):
                batch = x[idx[start : start + batch_size]]
                recon = model(batch)
                loss = loss_fn(recon, batch)
                opt.zero_grad()
                loss.backward()
                opt.step()

        # Threshold = ``threshold_pct``-th percentile of per-window reconstruction MSE.
        # The default (99) keeps the per-sample false-positive rate ~1% and
        # combines with the consumer-side cooldown to stay well below the
        # alert-fatigue line on a 500-device fleet.
        model.eval()
        with torch.no_grad():
            recon = model(x)
            errs = ((recon - x) ** 2).mean(dim=(1, 2)).cpu().numpy()
        threshold = float(np.percentile(errs, threshold_pct))

        return cls(model=model, mean=mean, std=std, threshold=threshold)

    def predict(self, window: list[dict]) -> tuple[bool, float]:
        """Returns ``(is_anomaly, reconstruction_error)``."""
        if len(window) < self.window_size:
            return False, 0.0
        seq = np.stack([vectorize(s) for s in window[-self.window_size :]])
        norm = (seq - self.mean) / self.std
        with torch.no_grad():
            x = torch.tensor(norm, dtype=torch.float32).unsqueeze(0)
            recon = self.model(x)
            err = float(((recon - x) ** 2).mean().item())
        return err > self.threshold, err

    def save(self, dir_path: Path) -> None:
        dir_path.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), dir_path / "lstm_ae.pt")
        meta = {
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "threshold": self.threshold,
            "window_size": self.window_size,
        }
        (dir_path / "lstm_ae.json").write_text(json.dumps(meta))

    @classmethod
    def load(cls, dir_path: Path) -> "LSTMAutoencoderDetector":
        meta = json.loads((dir_path / "lstm_ae.json").read_text())
        model = LSTMAutoencoder()
        model.load_state_dict(torch.load(dir_path / "lstm_ae.pt", map_location="cpu"))
        model.eval()
        return cls(
            model=model,
            mean=np.array(meta["mean"], dtype=np.float32),
            std=np.array(meta["std"], dtype=np.float32),
            threshold=float(meta["threshold"]),
            window_size=int(meta["window_size"]),
        )

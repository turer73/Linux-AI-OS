"""
train_ai_model.py - I/O decision model training

Supports two backends:
  - scikit-learn (default, lightweight, ~50 MB RAM)
  - torch LSTM (optional, for higher accuracy, ~500 MB RAM)

Usage:
  train-ai-model                    # scikit-learn (recommended for low-spec)
  train-ai-model --backend torch    # PyTorch LSTM (requires: pip install torch)
"""

import os
import argparse
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestClassifier
import pickle
import warnings

# Label mapping
LABELS = {
    "IDLE": 0,
    "READ_FOCUS": 1,
    "WRITE_PRIORITY": 2,
    "OPTIMIZE_BALANCE": 3
}

# Settings
LOG_FILE = "ai_lfs_log.csv"
SKLEARN_MODEL_PATH = "ai_model.pkl"
TORCH_MODEL_PATH = "ai_model.pt"
SCALER_PATH = "ai_scaler.pkl"


def load_and_prepare_data(log_file):
    df = pd.read_csv(log_file)
    df = df.dropna()

    X = df[["read_bytes", "write_bytes"]].values
    y = df["ai_decision"].map(LABELS).values

    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)

    return X_scaled, y, scaler


def train_sklearn(X, y, scaler):
    """Train lightweight RandomForest model (~2 MB model, <100 MB RAM)"""
    print("[TRAIN] sklearn RandomForest egitimi baslatildi...")

    model = RandomForestClassifier(
        n_estimators=50,       # light: 50 trees instead of 100
        max_depth=10,          # limit depth for memory
        n_jobs=2,              # max 2 cores on i7-M640
        random_state=42
    )
    model.fit(X, y)

    with open(SKLEARN_MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)

    accuracy = model.score(X, y)
    model_size = os.path.getsize(SKLEARN_MODEL_PATH) / 1024
    print(f"[TRAIN] Accuracy: {accuracy:.4f}")
    print(f"[TRAIN] Model boyutu: {model_size:.1f} KB")
    print(f"[TRAIN] Model kaydedildi: {SKLEARN_MODEL_PATH}")


def train_torch(X, y, scaler):
    """Train LSTM model (requires torch, ~500 MB RAM)"""
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        print("[TRAIN] HATA: PyTorch yuklu degil.")
        print("[TRAIN] Kurmak icin: pip install torch")
        print("[TRAIN] Veya hafif mod kullanin: train-ai-model --backend sklearn")
        return

    class IOModel(nn.Module):
        def __init__(self, input_size=2, hidden_size=32, output_size=4):
            super(IOModel, self).__init__()
            self.lstm = nn.LSTM(input_size, hidden_size, batch_first=True)
            self.fc = nn.Linear(hidden_size, output_size)

        def forward(self, x):
            out, _ = self.lstm(x)
            out = self.fc(out[:, -1, :])
            return out

    print("[TRAIN] PyTorch LSTM egitimi baslatildi...")

    X_seq = np.expand_dims(X, axis=1)
    X_tensor = torch.tensor(X_seq, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.long)

    model = IOModel(input_size=2, hidden_size=32, output_size=4)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    epochs = 30
    batch_size = 16

    for epoch in range(epochs):
        permutation = torch.randperm(X_tensor.size(0))
        total_loss = 0

        for i in range(0, X_tensor.size(0), batch_size):
            indices = permutation[i:i + batch_size]
            batch_x, batch_y = X_tensor[indices], y_tensor[indices]

            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        if (epoch + 1) % 10 == 0:
            print(f"[TRAIN] Epoch {epoch + 1}/{epochs}, Loss: {total_loss:.4f}")

    torch.save(model.state_dict(), TORCH_MODEL_PATH)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)

    print(f"[TRAIN] Model kaydedildi: {TORCH_MODEL_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Linux-AI I/O model egitimi")
    parser.add_argument("--backend", choices=["sklearn", "torch"], default="sklearn",
                        help="Egitim backend'i (varsayilan: sklearn)")
    args = parser.parse_args()

    if not os.path.exists(LOG_FILE):
        print(f"[TRAIN] Log dosyasi bulunamadi: {LOG_FILE}")
        print("[TRAIN] Once veri olusturun: simulate-io-stats")
        return

    X, y, scaler = load_and_prepare_data(LOG_FILE)
    print(f"[TRAIN] {len(y)} ornek yuklendi.")

    if args.backend == "torch":
        train_torch(X, y, scaler)
    else:
        train_sklearn(X, y, scaler)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()

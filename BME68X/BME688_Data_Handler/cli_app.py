"""
Simple terminal application for training and using a linear-regression classifier
with BME688 sensor data. The app has two core actions:

    1. Train from a CSV file that contains sensor samples and a `Label_Tag` column.
    2. Load a saved model and classify new samples streamed over a serial port.

The CSV used for training must match the live serial format (same columns/order),
because the real-time classifier expects identical column names when parsing.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import serial
import serial.tools.list_ports
from joblib import dump, load
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

LABEL_COLUMN = "Label_Tag"
SERIAL_BAUD_RATE = 115200


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def _prompt_with_default(prompt: str, default: str) -> str:
    response = input(f"{prompt} [{default}]: ").strip()
    return response or default


def _list_serial_ports() -> List[str]:
    ports = [port.device for port in serial.tools.list_ports.comports()]
    return ports


def _to_float(value) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _load_training_csv(csv_path: str) -> pd.DataFrame:
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    df = pd.read_csv(csv_path)
    if LABEL_COLUMN not in df.columns:
        raise ValueError(f"CSV file must include a '{LABEL_COLUMN}' column.")
    return df


def _prepare_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Convert all non-label columns to numeric features, dropping empty ones."""
    feature_candidates = df.drop(columns=[LABEL_COLUMN], errors="ignore")
    numeric_data = {}
    for col in feature_candidates.columns:
        numeric_series = pd.to_numeric(feature_candidates[col], errors="coerce")
        if numeric_series.notna().sum() == 0:
            continue
        numeric_data[col] = numeric_series.fillna(0.0)
    return pd.DataFrame(numeric_data)


def _build_feature_row(record: Dict[str, object], feature_columns: Sequence[str]) -> pd.DataFrame:
    row = {col: _to_float(record.get(col, 0.0)) for col in feature_columns}
    return pd.DataFrame([row], columns=feature_columns)


def _parse_serial_line(line: str, columns: Sequence[str]) -> Optional[Dict[str, str]]:
    try:
        values = next(csv.reader([line]))
    except Exception:
        return None
    if len(values) < len(columns):
        return None
    return dict(zip(columns, values))


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train_model():
    default_csv_path = str(BASE_DIR / "DataCollection" / "test.csv")
    csv_path = _prompt_with_default("Path to training CSV", default_csv_path)

    try:
        df_raw = _load_training_csv(csv_path)
    except Exception as exc:
        print(f"Failed to load CSV: {exc}")
        return

    source_columns = list(df_raw.columns)
    feature_df = _prepare_feature_matrix(df_raw)
    if feature_df.empty:
        print("No numeric features were found in the CSV.")
        return

    labels = df_raw[LABEL_COLUMN].astype(str)
    if labels.nunique() < 2:
        print("Need at least two distinct labels to train the classifier.")
        return

    encoder = LabelEncoder()
    y_encoded = encoder.fit_transform(labels.values)

    model = LinearRegression()
    model.fit(feature_df.values, y_encoded)

    train_predictions = model.predict(feature_df.values)
    predicted_indices = np.clip(np.rint(train_predictions), 0, len(encoder.classes_) - 1).astype(int)
    training_accuracy = (predicted_indices == y_encoded).mean()
    print(f"Training accuracy (rounded predictions): {training_accuracy:.3f}")

    artifact = {
        "model": model,
        "label_encoder": encoder,
        "feature_columns": list(feature_df.columns),
        "source_columns": source_columns,
        "trained_at": dt.datetime.now().isoformat(),
    }

    default_model_path = MODEL_DIR / "bme688_linear.joblib"
    model_path = _prompt_with_default("Path to save model", str(default_model_path))
    try:
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        dump(artifact, model_path)
        print(f"Model saved to {model_path}")
    except Exception as exc:
        print(f"Failed to save model: {exc}")


# ---------------------------------------------------------------------------
# Real-time classification
# ---------------------------------------------------------------------------
def run_realtime_classification():
    default_model_path = MODEL_DIR / "bme688_linear.joblib"
    model_path = _prompt_with_default("Path to trained model", str(default_model_path))
    if not os.path.isfile(model_path):
        print(f"Model file not found: {model_path}")
        return

    try:
        artifact = load(model_path)
    except Exception as exc:
        print(f"Failed to load model artifact: {exc}")
        return

    required_keys = {"model", "label_encoder", "feature_columns", "source_columns"}
    if not required_keys.issubset(artifact.keys()):
        print("Model artifact missing metadata. Retrain the model.")
        return

    model: LinearRegression = artifact["model"]
    encoder: LabelEncoder = artifact["label_encoder"]
    feature_columns: Sequence[str] = artifact["feature_columns"]
    source_columns: Sequence[str] = artifact["source_columns"]

    ports = _list_serial_ports()
    if ports:
        print("Available serial ports:")
        for idx, device in enumerate(ports, start=1):
            print(f"  {idx}. {device}")
    else:
        print("No serial ports detected.")

    port_name = input("Serial port to use (e.g., COM3 or /dev/ttyUSB0): ").strip()
    if not port_name:
        print("Serial port is required.")
        return

    try:
        ser = serial.Serial(port_name, SERIAL_BAUD_RATE, timeout=1)
        time.sleep(2)
    except serial.SerialException as exc:
        print(f"Failed to open serial port: {exc}")
        return

    send_start = input("Send 'START' command to device? [y/N]: ").strip().lower() == "y"
    if send_start:
        try:
            ser.write(b"START\n")
        except serial.SerialException as exc:
            print(f"Unable to send START command: {exc}")

    print("Streaming data. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                raw_line = ser.readline().decode(errors="ignore").strip()
            except serial.SerialException as exc:
                print(f"Serial read error: {exc}")
                break

            if not raw_line:
                continue

            record = _parse_serial_line(raw_line, source_columns)
            if not record:
                continue

            feature_vector = _build_feature_row(record, feature_columns)
            try:
                pred_value = model.predict(feature_vector.values)[0]
            except Exception as exc:
                print(f"Prediction failed: {exc}")
                continue

            pred_index = int(np.clip(np.rint(pred_value), 0, len(encoder.classes_) - 1))
            pred_label = encoder.inverse_transform([pred_index])[0]
            timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            actual_label = record.get(LABEL_COLUMN)
            actual_display = f" | Actual: {actual_label}" if actual_label else ""
            print(f"[{timestamp}] Prediction: {pred_label}{actual_display}")
    except KeyboardInterrupt:
        print("\nStopping real-time classification...")
    finally:
        if send_start:
            try:
                ser.write(b"STOP\n")
            except serial.SerialException:
                pass
        ser.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    actions = {
        "1": ("Train model from CSV", train_model),
        "2": ("Run real-time classification", run_realtime_classification),
        "3": ("Exit", None),
    }

    while True:
        print("\nBME688 Linear CLI")
        for key, (label, _) in actions.items():
            print(f"{key}. {label}")

        choice = input("Select an option: ").strip()
        if choice == "3":
            print("Goodbye.")
            break
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        action[1]()  # type: ignore[misc]


if __name__ == "__main__":
    main()

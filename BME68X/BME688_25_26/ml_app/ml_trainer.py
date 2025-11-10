#!/usr/bin/env python3
"""
Standalone ML training utility with model selection and accuracy reporting.

Example:
    python ml_trainer.py --data data.csv --target Label --model random_forest
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent
MPL_CACHE_DIR = BASE_DIR / ".mpl-cache"
CACHE_DIR = BASE_DIR / ".cache"
for directory in (MPL_CACHE_DIR, CACHE_DIR):
    directory.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    AdaBoostClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC

RANDOM_STATE = 42
MODEL_CHOICES = [
    "logistic_regression",
    "random_forest",
    "svm",
    "knn",
    "gradient_boosting",
    "adaboost",
    "extra_trees",
    "mlp",
]
RUN_DIR = BASE_DIR / "training_runs"
RUN_DIR.mkdir(parents=True, exist_ok=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a classification model with evaluation reports."
    )
    parser.add_argument(
        "--data",
        type=Path,
        required=True,
        help="Path to the input CSV dataset.",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Name of the target column to predict.",
    )
    parser.add_argument(
        "--model",
        choices=MODEL_CHOICES,
        default="random_forest",
        help="Classifier to train.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Fraction of samples reserved for testing (default: 0.2).",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Directory to write reports (default: ml_app/training_runs/<timestamp>).",
    )
    return parser


def load_dataset(csv_path: Path, target_col: str) -> Tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(csv_path)
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in {csv_path.name}.")
    if df[target_col].isna().any():
        raise ValueError("Target column contains missing values. Clean the data first.")
    features = df.drop(columns=[target_col])
    labels = df[target_col]
    if features.empty:
        raise ValueError("Dataset must include at least one feature column.")
    return features, labels


def build_preprocessor(feature_frame: pd.DataFrame) -> Tuple[ColumnTransformer, List[str], List[str]]:
    numeric_cols = feature_frame.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [col for col in feature_frame.columns if col not in numeric_cols]
    transformers = []
    if numeric_cols:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_cols,
            )
        )
    if categorical_cols:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_cols,
            )
        )
    if not transformers:
        raise ValueError("Could not determine numeric or categorical feature columns.")
    preprocessor = ColumnTransformer(transformers=transformers)
    return preprocessor, numeric_cols, categorical_cols


def build_model_factory() -> Dict[str, Callable[[], Any]]:
    return {
        "logistic_regression": lambda: LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=400,
            max_depth=None,
            min_samples_split=2,
            random_state=RANDOM_STATE,
        ),
        "svm": lambda: SVC(kernel="rbf", C=1.0, gamma="scale", probability=True, random_state=RANDOM_STATE),
        "knn": lambda: KNeighborsClassifier(n_neighbors=7, weights="distance"),
        "gradient_boosting": lambda: GradientBoostingClassifier(random_state=RANDOM_STATE),
        "adaboost": lambda: AdaBoostClassifier(n_estimators=200, random_state=RANDOM_STATE),
        "extra_trees": lambda: ExtraTreesClassifier(
            n_estimators=400, max_depth=None, random_state=RANDOM_STATE, n_jobs=-1
        ),
        "mlp": lambda: MLPClassifier(
            hidden_layer_sizes=(256, 128),
            activation="relu",
            alpha=1e-4,
            learning_rate="adaptive",
            max_iter=500,
            random_state=RANDOM_STATE,
        ),
    }


def train_and_evaluate(
    model_name: str,
    features: pd.DataFrame,
    labels: pd.Series,
    test_size: float,
) -> Dict:
    preprocessor, numeric_cols, categorical_cols = build_preprocessor(features)
    models = build_model_factory()
    estimator = models[model_name]()
    pipeline = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            ("classifier", estimator),
        ]
    )
    stratify = labels if labels.nunique() > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=test_size,
        random_state=RANDOM_STATE,
        stratify=stratify,
    )
    pipeline.fit(X_train, y_train)
    predictions = pipeline.predict(X_test)
    acc = accuracy_score(y_test, predictions)
    labels_sorted = sorted(labels.unique())
    cm = confusion_matrix(y_test, predictions, labels=labels_sorted)
    cls_report_dict = classification_report(
        y_test,
        predictions,
        labels=labels_sorted,
        output_dict=True,
        zero_division=0,
    )
    return {
        "pipeline": pipeline,
        "accuracy": acc,
        "confusion_matrix": cm,
        "classification_report_dict": cls_report_dict,
        "y_test": y_test,
        "predictions": predictions,
        "labels": labels_sorted,
        "feature_breakdown": {
            "numeric_features": numeric_cols,
            "categorical_features": categorical_cols,
        },
        "train_samples": len(X_train),
        "test_samples": len(X_test),
    }


def _render_confusion_matrix_image(confusion: np.ndarray, labels: List[Any]) -> io.BytesIO:
    buffer = io.BytesIO()
    plt.figure(figsize=(6, 5))
    sns.heatmap(
        confusion,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels,
    )
    plt.xlabel("Predicted label")
    plt.ylabel("True label")
    plt.title("Confusion Matrix")
    plt.tight_layout()
    plt.savefig(buffer, format="PNG", dpi=200)
    plt.close()
    buffer.seek(0)
    return buffer


def generate_pdf_report(result: Dict, report_dir: Path, model_name: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = report_dir / "training_report.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        title="BME688 ML Training Report",
        leftMargin=36,
        rightMargin=36,
        topMargin=48,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("BME688 ML Training Report", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Model: <b>{model_name}</b>", styles["Heading2"]))
    story.append(Paragraph(f"Generated: {dt.datetime.now().isoformat(sep=' ', timespec='seconds')}", styles["BodyText"]))
    story.append(Spacer(1, 12))

    summary_data = [
        ["Accuracy", f"{result['accuracy']:.3f}"],
        ["Train Samples", str(result["train_samples"])],
        ["Test Samples", str(result["test_samples"])],
        ["Labels", ", ".join(map(str, result["labels"]))],
    ]
    summary_table = Table(summary_data, colWidths=[150, 330])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 18))

    story.append(Paragraph("Classification Metrics", styles["Heading2"]))
    cls_rows = [["Class", "Precision", "Recall", "F1-Score", "Support"]]
    cls_dict = result["classification_report_dict"]
    for label, metrics in cls_dict.items():
        if label in {"accuracy"}:
            continue
        precision = metrics.get("precision", 0.0)
        recall = metrics.get("recall", 0.0)
        f1_score = metrics.get("f1-score", 0.0)
        support = metrics.get("support", 0)
        cls_rows.append(
            [
                label,
                f"{precision:.3f}",
                f"{recall:.3f}",
                f"{f1_score:.3f}",
                f"{int(support)}",
            ]
        )
    cls_table = Table(cls_rows, repeatRows=1, hAlign="LEFT")
    cls_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f77b4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ]
        )
    )
    story.append(cls_table)
    story.append(Spacer(1, 18))

    story.append(Paragraph("Confusion Matrix", styles["Heading2"]))
    cm_buffer = _render_confusion_matrix_image(result["confusion_matrix"], result["labels"])
    cm_image = RLImage(cm_buffer, width=380, height=320)
    story.append(cm_image)

    doc.build(story)
    return pdf_path


def save_model(pipeline: Pipeline, report_dir: Path) -> Path:
    try:
        import joblib
    except ImportError as exc:
        raise RuntimeError(
            "joblib is required to save the trained pipeline. Install it via pip."
        ) from exc
    model_path = report_dir / "trained_pipeline.joblib"
    joblib.dump(pipeline, model_path)
    return model_path


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    report_dir = args.report_dir or RUN_DIR / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    features, labels = load_dataset(args.data, args.target)
    if not 0 < args.test_size < 0.9:
        raise ValueError("--test-size must be between 0 and 0.9.")
    result = train_and_evaluate(
        model_name=args.model,
        features=features,
        labels=labels,
        test_size=args.test_size,
    )
    pdf_report = generate_pdf_report(result, report_dir, args.model)
    model_path = save_model(result["pipeline"], report_dir)
    print(f"Model: {args.model}")
    print(f"Accuracy: {result['accuracy']:.3f}")
    print(f"Train samples: {result['train_samples']} | Test samples: {result['test_samples']}")
    print(f"Labels: {', '.join(map(str, result['labels']))}")
    print(f"Report: {pdf_report}")
    print(f"Serialized pipeline: {model_path}")


if __name__ == "__main__":
    main()

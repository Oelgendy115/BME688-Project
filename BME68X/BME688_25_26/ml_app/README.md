# ML Training Utility

This standalone Python application trains and evaluates classification models on
CSV datasets. It automatically handles preprocessing (numeric scaling and
categorical encoding), offers multiple model choices (tree-based, boosting, and
neural networks), and produces a polished PDF report that summarizes the results
(including a confusion matrix) alongside a serialized scikit-learn pipeline.

## Setup

```bash
cd ml_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python ml_trainer.py \
  --data path/to/dataset.csv \
  --target TargetColumn \
  --model random_forest \
  --test-size 0.25
```

### GUI Mode

If you prefer a graphical interface, launch:

```bash
python ml_trainer_gui.py
```

The GUI lets you browse for a CSV file, load available columns, pick the target,
choose a model, and configure the test split. After training, it displays the
accuracy summary along with the generated confusion-matrix plot (unless you
opt out).

### Arguments

- `--data` *(required)*: CSV file containing features and the target column.
- `--target` *(required)*: Column name in the CSV to predict.
- `--model`: Choose from `logistic_regression`, `random_forest`, `svm`, `knn`,
  `gradient_boosting`, `adaboost`, `extra_trees`, or `mlp` (multi-layer perceptron).
- `--test-size`: Fraction of rows used for evaluation (default `0.2`).
- `--report-dir`: Optional directory for outputs (defaults to
  `ml_app/training_runs/<timestamp>`).

## Outputs

Each training run now outputs:

- `training_report.pdf`: A branded PDF containing accuracy, dataset splits,
  per-class precision/recall/F1, and the confusion matrix heatmap.
- `trained_pipeline.joblib`: Complete preprocessing + model pipeline ready for
  reuse on new data.

## Notes

- The dataset must be a CSV with at least one feature column and no missing
  values in the target column.
- Numeric predictors are scaled and median-imputed; categorical predictors are
  one-hot encoded with most-frequent imputation.
- Re-run the command with different `--model` values to compare performance
  using the consistent preprocessing pipeline.

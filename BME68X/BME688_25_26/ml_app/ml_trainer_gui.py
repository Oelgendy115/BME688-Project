#!/usr/bin/env python3
"""
Graphical interface for training ML models with selectable algorithms and reports.
"""
from __future__ import annotations

import datetime as dt
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from ml_trainer import MODEL_CHOICES, RUN_DIR, generate_pdf_report, load_dataset, save_model, train_and_evaluate


class TrainerGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("BME688 ML Trainer")
        self.root.geometry("900x640")

        self.data_path_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.model_var = tk.StringVar(value=MODEL_CHOICES[0])
        self.test_size_var = tk.StringVar(value="0.2")
        self.report_dir_var = tk.StringVar()
        self.report_path_var = tk.StringVar(value="Report not generated yet.")

        self.training_thread: threading.Thread | None = None

        self._build_layout()

    # ------------------------------------------------------------------ UI setup
    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        # Dataset path
        ttk.Label(container, text="Dataset CSV:").grid(row=0, column=0, sticky="w")
        data_entry = ttk.Entry(container, textvariable=self.data_path_var, width=60)
        data_entry.grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(container, text="Browse…", command=self._select_dataset).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(container, text="Load Columns", command=self._load_columns).grid(
            row=0, column=3, padx=4
        )

        # Target column
        ttk.Label(container, text="Target Column:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.target_combo = ttk.Combobox(
            container,
            textvariable=self.target_var,
            state="readonly",
            width=30,
        )
        self.target_combo.grid(row=1, column=1, sticky="w", padx=6, pady=(8, 0))

        # Model selection
        ttk.Label(container, text="Model:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        model_combo = ttk.Combobox(
            container,
            values=MODEL_CHOICES,
            textvariable=self.model_var,
            state="readonly",
            width=30,
        )
        model_combo.grid(row=2, column=1, sticky="w", padx=6, pady=(8, 0))

        # Test size
        ttk.Label(container, text="Test Size (0-0.9):").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(container, textvariable=self.test_size_var, width=10).grid(
            row=3, column=1, sticky="w", padx=6, pady=(8, 0)
        )

        # Report dir
        ttk.Label(container, text="Report Directory (optional):").grid(
            row=4, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(container, textvariable=self.report_dir_var, width=60).grid(
            row=4, column=1, sticky="we", padx=6, pady=(8, 0)
        )
        ttk.Button(container, text="Browse…", command=self._select_report_dir).grid(
            row=4, column=2, padx=4, pady=(8, 0)
        )

        # Train button
        self.train_button = ttk.Button(container, text="Train Model", command=self._run_training)
        self.train_button.grid(row=5, column=0, columnspan=2, pady=10, sticky="we")

        ttk.Separator(container).grid(row=6, column=0, columnspan=4, sticky="we", pady=12)

        # Status/log output
        ttk.Label(container, text="Training Log:").grid(row=7, column=0, sticky="w")
        self.log_text = tk.Text(container, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=8, column=0, columnspan=4, sticky="nsew")
        log_scroll = ttk.Scrollbar(container, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.grid(row=8, column=4, sticky="ns")

        ttk.Label(container, text="Latest Report:").grid(row=9, column=0, sticky="w", pady=(12, 4))
        self.report_label = ttk.Label(
            container,
            textvariable=self.report_path_var,
            wraplength=600,
            foreground="#1f77b4",
        )
        self.report_label.grid(row=10, column=0, columnspan=4, sticky="w")

        container.columnconfigure(1, weight=1)
        container.rowconfigure(8, weight=1)

    # ------------------------------------------------------------------ helpers
    def _select_dataset(self) -> None:
        filepath = filedialog.askopenfilename(
            title="Select dataset CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if filepath:
            self.data_path_var.set(filepath)
            self._load_columns()

    def _load_columns(self) -> None:
        dataset = self.data_path_var.get().strip()
        if not dataset:
            messagebox.showwarning("Select dataset", "Please choose a dataset CSV first.")
            return
        try:
            header_df = pd.read_csv(dataset, nrows=0)
        except Exception as exc:
            messagebox.showerror("Error reading CSV", str(exc))
            return
        columns = header_df.columns.tolist()
        if not columns:
            messagebox.showerror("Missing columns", "No columns detected in the CSV file.")
            return
        self.target_combo.configure(values=columns)
        if columns:
            self.target_combo.set(columns[-1])
        self._log(f"Loaded columns: {', '.join(columns)}")

    def _select_report_dir(self) -> None:
        directory = filedialog.askdirectory(title="Select report directory")
        if directory:
            self.report_dir_var.set(directory)

    def _log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.configure(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def _toggle_inputs(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.train_button.configure(state=state)

    # ------------------------------------------------------------------ training
    def _run_training(self) -> None:
        if self.training_thread and self.training_thread.is_alive():
            messagebox.showinfo("Training in progress", "Please wait for the current run to finish.")
            return

        dataset = Path(self.data_path_var.get().strip()).expanduser()
        target = self.target_var.get().strip()
        try:
            test_size = float(self.test_size_var.get())
        except ValueError:
            messagebox.showerror("Invalid test size", "Test size must be a number between 0 and 0.9.")
            return

        if not dataset.exists():
            messagebox.showerror("Dataset missing", f"File not found: {dataset}")
            return
        if not target:
            messagebox.showerror("Target column", "Please choose a target column.")
            return
        if not 0 < test_size < 0.9:
            messagebox.showerror("Test size", "Please use a value between 0 and 0.9.")
            return

        report_dir_input = self.report_dir_var.get().strip()
        report_dir = (
            Path(report_dir_input)
            if report_dir_input
            else RUN_DIR / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        model_choice = self.model_var.get()

        self._toggle_inputs(False)
        self._log(f"Starting training with {model_choice}...")
        self.training_thread = threading.Thread(
            target=self._train_worker,
            args=(dataset, target, test_size, model_choice, report_dir),
            daemon=True,
        )
        self.training_thread.start()

    def _train_worker(
        self,
        dataset: Path,
        target: str,
        test_size: float,
        model_choice: str,
        report_dir: Path,
    ) -> None:
        try:
            features, labels = load_dataset(dataset, target)
            result = train_and_evaluate(
                model_name=model_choice,
                features=features,
                labels=labels,
                test_size=test_size,
            )
            pdf_report = generate_pdf_report(result, report_dir, model_choice)
            model_path = save_model(result["pipeline"], report_dir)
        except Exception as exc:  # pylint: disable=broad-except
            self.root.after(0, lambda err=exc: self._handle_failure(err))
            return

        self.root.after(
            0,
            lambda: self._handle_success(
                model_choice=model_choice,
                report_dir=report_dir,
                pdf_report=pdf_report,
                accuracy=result["accuracy"],
                train_samples=result["train_samples"],
                test_samples=result["test_samples"],
                model_path=model_path,
            ),
        )

    def _handle_failure(self, exc: Exception) -> None:
        self._log(f"Error: {exc}")
        messagebox.showerror("Training failed", str(exc))
        self._toggle_inputs(True)

    def _handle_success(
        self,
        model_choice: str,
        report_dir: Path,
        pdf_report: Path,
        accuracy: float,
        train_samples: int,
        test_samples: int,
        model_path: Path,
    ) -> None:
        self._log(f"Model: {model_choice}")
        self._log(f"Accuracy: {accuracy:.3f}")
        self._log(f"Train samples: {train_samples} | Test samples: {test_samples}")
        self._log(f"Reports stored at: {pdf_report}")
        self._log(f"Serialized pipeline: {model_path}")
        self.report_path_var.set(str(pdf_report))
        messagebox.showinfo("Training complete", f"Accuracy: {accuracy:.3f}\nReport: {pdf_report}")
        self._toggle_inputs(True)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    TrainerGUI().run()


if __name__ == "__main__":
    main()

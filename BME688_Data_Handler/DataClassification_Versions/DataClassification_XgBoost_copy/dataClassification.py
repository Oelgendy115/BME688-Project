import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import pandas as pd
import json
from joblib import dump, load
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder
import serial
import serial.tools.list_ports
import threading
import time
import csv
from io import StringIO
import numpy as np
from statistics import mode
from xgboost import XGBClassifier

from dataProcessor import DataProcessor, FEATURES

METRICS_FILE = "model_metrics.json"

WINDOW_SIZE = 5
STRIDE = 1
MAX_WINDOW = 10

class ModelTrainerGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Data Classification GUI")
        self.master.geometry("1000x700")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        self.raw_data_file = tk.StringVar()
        self.status = tk.StringVar(value="Status: Idle")
        self.prediction_file = tk.StringVar()
        self.model_path = "data_classifier_model.joblib"
        self.model_metrics = None
        self.df_for_training = None

        # Real-time variables
        self.rt_serial_port = None
        self.rt_connected = False
        self.rt_logging = False
        self.rt_stop_event = threading.Event()
        self.rt_data_buffer = []
        self.batch_length_var = tk.StringVar(value="5")
        self.time_left_var = tk.StringVar(value="0")
        self.current_prediction = tk.StringVar(value="N/A")

        main_frame = tk.Frame(master)
        main_frame.grid(sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)

        ####################################################################
        # 1) TRAIN MODEL FRAME
        ####################################################################
        train_model_frame = tk.LabelFrame(main_frame, text="1. Train Model", padx=10, pady=10)
        train_model_frame.grid(row=0, column=0, sticky="ew", pady=5)
        # Configure columns: 0 for Label, 1 for Entry, 2 for Browse
        train_model_frame.columnconfigure(0, weight=0)
        train_model_frame.columnconfigure(1, weight=1)
        train_model_frame.columnconfigure(2, weight=0)

        # Row 0: Label/File Entry/Browse
        tk.Label(train_model_frame, text="Raw Data File:").grid(row=0, column=0, sticky="w")
        tk.Entry(train_model_frame, textvariable=self.raw_data_file).grid(row=0, column=1, padx=5, sticky="ew")
        tk.Button(train_model_frame, text="Browse", command=self.browse_file_train).grid(row=0, column=2, padx=5)

        # Row 1: Frame for Train Button and Progress Bar
        train_buttons_frame = tk.Frame(train_model_frame)
        train_buttons_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
        train_buttons_frame.columnconfigure(0, weight=0)  # Train Button
        train_buttons_frame.columnconfigure(1, weight=1)  # Progress Bar

        self.train_button = tk.Button(train_buttons_frame, text="Train Model", command=self.train_model)
        self.train_button.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.train_progress_bar = ttk.Progressbar(train_buttons_frame, orient="horizontal", mode="determinate")
        self.train_progress_bar.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.train_progress_bar["maximum"] = 100
        self.train_progress_bar["value"] = 0

        ####################################################################
        # 2) MODEL PREDICTION FRAME
        ####################################################################
        predict_frame = tk.LabelFrame(main_frame, text="2. Model Prediction", padx=10, pady=10)
        predict_frame.grid(row=1, column=0, sticky="ew", pady=5)
        # Configure columns: 0 for Label, 1 for Entry, 2 for Browse
        predict_frame.columnconfigure(0, weight=0)
        predict_frame.columnconfigure(1, weight=1)
        predict_frame.columnconfigure(2, weight=0)

        # Row 0: Label/File Entry/Browse
        tk.Label(predict_frame, text="Prediction Input File:").grid(row=0, column=0, sticky="w")
        tk.Entry(predict_frame, textvariable=self.prediction_file).grid(row=0, column=1, padx=5, sticky="ew")
        tk.Button(predict_frame, text="Browse", command=self.browse_file_predict).grid(row=0, column=2, padx=5)

        # Row 1: Frame for Predict Button, Show Metrics Button, and Progress Bar
        predict_buttons_frame = tk.Frame(predict_frame)
        predict_buttons_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
        predict_buttons_frame.columnconfigure(0, weight=0)  # Predict Button
        predict_buttons_frame.columnconfigure(1, weight=0)  # Show Metrics Button
        predict_buttons_frame.columnconfigure(2, weight=1)  # Progress Bar

        self.predict_button = tk.Button(predict_buttons_frame, text="Predict", command=self.predict_data)
        self.predict_button.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.show_metrics_button = tk.Button(predict_buttons_frame, text="Show Metrics", command=self.display_metrics)
        self.show_metrics_button.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.show_metrics_button.config(state=tk.DISABLED)  # Enabled after we have actual metrics

        self.predict_progress_bar = ttk.Progressbar(predict_buttons_frame, orient="horizontal", mode="determinate")
        self.predict_progress_bar.grid(row=0, column=2, padx=10, pady=5, sticky="ew")
        self.predict_progress_bar["maximum"] = 100
        self.predict_progress_bar["value"] = 0

        ####################################################################
        # 3) REAL-TIME PREDICTIONS FRAME
        ####################################################################
        rt_frame = tk.LabelFrame(main_frame, text="3. Real-time Predictions", padx=10, pady=10)
        rt_frame.grid(row=2, column=0, sticky="ew", pady=5)
        rt_frame.columnconfigure(1, weight=1)
        rt_frame.columnconfigure(4, weight=1)

        tk.Label(rt_frame, text="Select Port:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.rt_port_var = tk.StringVar()
        ports = self.get_serial_ports()
        if ports:
            self.rt_port_var.set(ports[0])
            self.rt_port_dropdown = tk.OptionMenu(rt_frame, self.rt_port_var, *ports)
        else:
            self.rt_port_var.set("")
            self.rt_port_dropdown = tk.OptionMenu(rt_frame, self.rt_port_var, "")
        self.rt_port_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        tk.Button(rt_frame, text="Refresh Ports", command=self.refresh_rt_ports).grid(row=0, column=2, padx=5, pady=5)

        self.rt_connect_button = tk.Button(rt_frame, text="Connect", command=self.rt_connect_serial, width=10)
        self.rt_connect_button.grid(row=0, column=3, padx=5, pady=5)

        self.rt_disconnect_button = tk.Button(rt_frame, text="Disconnect", command=self.rt_disconnect_serial, state=tk.DISABLED, width=10)
        self.rt_disconnect_button.grid(row=0, column=4, padx=5, pady=5)

        tk.Label(rt_frame, text="Batch Length (sec):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(rt_frame, textvariable=self.batch_length_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        self.rt_start_button = tk.Button(rt_frame, text="Start Predictions", command=self.rt_start_predictions, state=tk.DISABLED, width=15)
        self.rt_start_button.grid(row=1, column=2, padx=5, pady=5)

        self.rt_stop_button = tk.Button(rt_frame, text="Stop Predictions", command=self.rt_stop_predictions, state=tk.DISABLED, width=15)
        self.rt_stop_button.grid(row=1, column=3, padx=5, pady=5)

        tk.Label(rt_frame, text="Seconds left in batch:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        tk.Label(rt_frame, textvariable=self.time_left_var, fg="blue").grid(row=2, column=1, padx=5, pady=5, sticky="w")

        rt_data_frame = tk.LabelFrame(rt_frame, text="Sensor Data Output", padx=10, pady=10)
        rt_data_frame.grid(row=3, column=0, columnspan=5, sticky="ew", padx=5, pady=5)
        rt_data_frame.columnconfigure(0, weight=1)
        self.rt_data_display = scrolledtext.ScrolledText(rt_data_frame, wrap=tk.WORD, height=5)
        self.rt_data_display.grid(row=0, column=0, sticky="nsew")

        pred_frame = tk.LabelFrame(rt_frame, text="Current Smell Prediction", padx=10, pady=10)
        pred_frame.grid(row=4, column=0, columnspan=5, sticky="ew", padx=5, pady=5)
        tk.Label(pred_frame, textvariable=self.current_prediction, fg="blue", font=("Helvetica", 12, "bold")).pack()

        ####################################################################
        # 4) TERMINAL UPDATES (STATUS) FRAME
        ####################################################################
        status_frame = tk.LabelFrame(main_frame, text="4. Terminal Updates", padx=10, pady=10)
        status_frame.grid(row=3, column=0, sticky="ew", pady=5)
        status_frame.columnconfigure(0, weight=1)

        self.status_label = tk.Label(status_frame, textvariable=self.status, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")

        ####################################################################
        # Finish Initialization
        ####################################################################
        self.update_status("Ready")
        self.load_metrics_from_file()


    ########################################################################
    # METRICS LOADING/SAVING
    ########################################################################
    def load_metrics_from_file(self):
        if os.path.exists(METRICS_FILE):
            try:
                with open(METRICS_FILE, "r") as f:
                    loaded_metrics = json.load(f)
                # Convert array-like confusion matrix if present
                if 'cm' in loaded_metrics:
                    loaded_metrics['cm'] = np.array(loaded_metrics['cm'])
                self.model_metrics = loaded_metrics
                # Enable "Show Metrics" button if there's prediction info
                if 'report' in loaded_metrics or 'cm' in loaded_metrics:
                    self.show_metrics_button.config(state=tk.NORMAL)
            except Exception:
                self.model_metrics = None

    def save_metrics_to_file(self, metrics):
        """
        Saves metrics to JSON, handling NumPy arrays as lists.
        """
        try:
            serializable_metrics = {}
            for key, value in metrics.items():
                if isinstance(value, np.ndarray):
                    serializable_metrics[key] = value.tolist()
                else:
                    serializable_metrics[key] = value
            with open(METRICS_FILE, "w") as f:
                json.dump(serializable_metrics, f, indent=4)
        except Exception:
            pass

    ########################################################################
    # BROWSE FILES
    ########################################################################
    def browse_file_train(self):
        filename = filedialog.askopenfilename(
            title="Select Raw Data File for Training",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            self.raw_data_file.set(filename)

    def browse_file_predict(self):
        filename = filedialog.askopenfilename(
            title="Select Input File for Prediction",
            filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
        )
        if filename:
            self.prediction_file.set(filename)

    ########################################################################
    # TRAIN MODEL
    ########################################################################
    def train_model(self):
        """
        1) Deletes any existing model/metrics.
        2) Processes data (progress bar up to 80%).
        3) Trains model on entire dataset (progress bar 80-100%).
        4) Saves model and metrics to file.
        """
        if not self.raw_data_file.get():
            messagebox.showerror("Error", "Please select a raw data file first.")
            return

        # Overwrite any existing model & metrics
        if os.path.exists(self.model_path):
            os.remove(self.model_path)
        if os.path.exists(METRICS_FILE):
            os.remove(METRICS_FILE)
        self.model_metrics = None

        self.update_status("Reading training file...")
        self.train_progress_bar["value"] = 0
        self.master.update_idletasks()

        try:
            processor = DataProcessor()
            df_for_training = processor.read_csv(self.raw_data_file.get())
        except Exception as e:
            messagebox.showerror("Error reading file", str(e))
            self.update_status("Idle")
            return

        self.update_status("Processing data...")
        thread = threading.Thread(target=self.run_training_bg, args=(df_for_training,))
        thread.daemon = True
        thread.start()

    def run_training_bg(self, df_for_training):
        """
        Runs in a background thread:
          - Detects if the file is raw or already processed.
          - Processes data (windows) if raw.
          - Encodes labels and computes sample weights to balance classes.
          - Checks if a previous grid search has already found the best hyperparameters.
            If not, it runs GridSearchCV; otherwise, it uses the saved parameters.
          - Trains an XGBoost classifier using these best parameters and sample weights.
          - Saves the trained model and updates a JSON metrics file with training info.
        """
        try:
            processor = DataProcessor()
            selected_features = list(FEATURES.keys())

            ################################################################
            # 1) DETECT IF RAW OR PROCESSED
            ################################################################
            lower_cols = [col.lower() for col in df_for_training.columns]

            if ('timestamp_ms' in lower_cols) and ('sensor1_temperature_deg_c' in lower_cols):
                self.master.after(0, lambda: self.update_status("Raw file detected. Processing data..."))
                processed_data = processor.process_data(
                    df_for_training,
                    window_size=WINDOW_SIZE,
                    stride=STRIDE,
                    selected_features=selected_features,
                    progress_callback=self.train_window_progress_callback
                )
                self.master.after(0, lambda: self.train_progress_bar.configure(value=80))
                self.master.after(0, lambda: self.update_status("Data processing completed. Training model..."))
                processed_df = pd.DataFrame(processed_data)
            else:
                self.master.after(0, lambda: self.update_status("Processed file detected. Skipping window processing..."))
                processed_df = df_for_training.copy()
                self.master.after(0, lambda: self.train_progress_bar.configure(value=80))

            if processed_df.empty:
                self.master.after(0, lambda: messagebox.showwarning("No Data", "No data available to train on."))
                self.master.after(0, lambda: self.update_status("Idle"))
                return

            ################################################################
            # 2) SAVE THE PROCESSED FILE
            ################################################################
            os.makedirs("Processed_Data", exist_ok=True)
            processed_file_path = os.path.join("Processed_Data", "processed_data.csv")
            processed_df.to_csv(processed_file_path, index=False)
            print(f"Saved processed features to: {processed_file_path}")

            ################################################################
            # 3) PREPARE DATA FOR TRAINING
            ################################################################
            ignore_cols = ['Label_Tag', 'Real_Time', 'WindowDurationSec']
            feature_cols = [c for c in processed_df.columns if c not in ignore_cols]

            X = processed_df[feature_cols]
            y_raw = processed_df['Label_Tag']

            # Encode labels (this will be used for predictions later)
            self.le = LabelEncoder()
            y = self.le.fit_transform(y_raw)

            ################################################################
            # 4) COMPUTE SAMPLE WEIGHTS FOR CLASS IMBALANCE
            ################################################################
            from sklearn.utils.class_weight import compute_class_weight
            classes = np.unique(y)
            # Compute a weight for each class (balanced)
            class_weights = compute_class_weight(class_weight='balanced', classes=classes, y=y)
            weight_dict = {cls: weight for cls, weight in zip(classes, class_weights)}
            # Build a sample_weight vector for every training sample
            sample_weights = np.array([weight_dict[label] for label in y])

            ################################################################
            # 5) OBTAIN BEST HYPERPARAMETERS (GRID SEARCH OR SAVED)
            ################################################################
            from sklearn.model_selection import GridSearchCV
            best_params = None
            best_score = None
            # Check if a previous metrics file exists with best parameters
            if os.path.exists(METRICS_FILE):
                try:
                    with open(METRICS_FILE, "r") as f:
                        saved_metrics = json.load(f)
                    if 'best_params' in saved_metrics:
                        best_params = saved_metrics['best_params']
                        best_score = saved_metrics.get('best_score', None)
                        print("Using previously saved best parameters:", best_params)
                        self.master.after(0, lambda: self.update_status("Using saved best hyperparameters."))
                except Exception as e:
                    print("Error reading METRICS_FILE:", e)

            # If not saved, run GridSearchCV to determine best parameters.
            if best_params is None:
                param_grid = {
                    'max_depth': [3, 5, 7],
                    'learning_rate': [0.01, 0.1, 0.2],
                    'n_estimators': [30, 50, 70],
                    'subsample': [0.8, 1.0],
                    'colsample_bytree': [0.8, 1.0]
                }
                grid = GridSearchCV(
                    estimator=XGBClassifier(random_state=42, use_label_encoder=False, eval_metric='mlogloss'),
                    param_grid=param_grid,
                    scoring='f1_weighted',
                    cv=3,
                    n_jobs=-1,
                    verbose=1,
                    refit=True
                )
                self.master.after(0, lambda: self.update_status("Performing GridSearchCV for hyperparameter tuning..."))
                grid.fit(X, y, sample_weight=sample_weights)
                best_params = grid.best_params_
                best_score = grid.best_score_
                self.master.after(0, lambda: self.update_status(f"GridSearchCV complete. Best score: {best_score:.4f}"))
            else:
                self.master.after(0, lambda: self.update_status("Using saved best hyperparameters from metrics file."))

            ################################################################
            # 6) TRAINING WITH XGBOOST USING BEST PARAMETERS
            ################################################################
            clf = XGBClassifier(
                random_state=42,
                use_label_encoder=False,
                eval_metric='mlogloss',
                **best_params
            )
            clf.fit(X, y, sample_weight=sample_weights)

            # Save the model along with the label encoder.
            dump((clf, self.le), self.model_path)

            ################################################################
            # 7) COLLECT LABEL METRICS AND SAVE HYPERPARAMETERS & WEIGHT INFO
            ################################################################
            label_info = {}
            group_obj = processed_df.groupby('Label_Tag')
            for label_val, group_df in group_obj:
                total_windows = len(group_df)
                label_info[label_val] = {'total_windows': total_windows}

            # Prepare a metrics dictionary including grid search information and weight dictionary.
            self.model_metrics = {
                "trained_on": os.path.basename(self.raw_data_file.get()),
                "label_info": label_info,
                "best_params": best_params,
                "best_score": best_score,
                "weight_dict": weight_dict
            }
            self.save_metrics_to_file(self.model_metrics)

            self.master.after(0, lambda: self.train_progress_bar.configure(value=100))
            self.master.after(
                0,
                lambda: self.update_status(
                    f"Training complete. Model saved. Trained on {os.path.basename(self.raw_data_file.get())}"
                )
            )

        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Training Error", str(e)))
            self.master.after(0, lambda: self.update_status("Idle"))
        finally:
            time.sleep(0.5)
            self.master.after(0, lambda: self.train_progress_bar.configure(value=0))

    def train_window_progress_callback(self, current, total):
        """
        Moves the progress bar from 0 to 80% as windows are processed.
        """
        if total == 0:
            progress = 0
        else:
            progress = (current / total) * 80
        self.master.after(0, lambda: self.train_progress_bar.configure(value=progress))

    ########################################################################
    # MODEL PREDICTION
    ########################################################################
    def predict_data(self):
        """
        1) Check for input file
        2) Process data (progress up to 80%)
        3) Predict (progress 80-100%)
        4) Show metrics if 'Label_Tag' exists
        """
        if not self.prediction_file.get():
            messagebox.showerror("Error", "Please select an input file for prediction.")
            return
        self.predict_progress_bar["value"] = 0
        self.update_status("Preparing to predict...")
        self.master.update_idletasks()

        if not os.path.exists(self.model_path):
            messagebox.showerror("Error", "No trained model found. Please train a model first.")
            self.update_status("Idle")
            return
        try:
            clf, le = load(self.model_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load model: {e}")
            self.update_status("Idle")
            return

        try:
            processor = DataProcessor()
            raw_df = processor.read_csv(self.prediction_file.get())
        except Exception as e:
            messagebox.showerror("Error", f"Error reading prediction file: {e}")
            self.update_status("Idle")
            return

        # Process data in a background thread
        thread = threading.Thread(target=self.run_prediction_bg, args=(raw_df, clf, le))
        thread.daemon = True
        thread.start()

    def run_prediction_bg(self, raw_df, clf, le):
        """
        Processes the data (windows) with a callback updating the progress bar to 80%,
        then performs predictions (80-100%), optionally computing metrics if Label_Tag is present.
        """
        try:
            self.master.after(0, lambda: self.update_status("Processing data for prediction..."))
            processor = DataProcessor()
            selected_features = list(FEATURES.keys())

            processed_data = processor.process_data(
                raw_df,
                window_size=WINDOW_SIZE,
                stride=STRIDE,
                selected_features=selected_features,
                progress_callback=self.predict_window_progress_callback
            )

            self.master.after(0, lambda: self.predict_progress_bar.configure(value=80))
            self.master.after(0, lambda: self.update_status("Data processed. Running predictions..."))

            processed_df = pd.DataFrame(processed_data)
            if processed_df.empty:
                self.master.after(0, lambda: messagebox.showwarning(
                    "No Data", "No data available for prediction after processing."))
                self.master.after(0, lambda: self.update_status("Idle"))
                return

            # Exclude Real_Time from features
            feature_cols = [c for c in processed_df.columns if c not in ['Label_Tag', 'Predicted_Label', 'Real_Time']]
            X_pred = processed_df[feature_cols]
            y_pred_numeric = clf.predict(X_pred)
            predictions = le.inverse_transform(y_pred_numeric)
            processed_df['Predicted_Label'] = predictions

            # If we have a Label_Tag, let's compute metrics
            if 'Label_Tag' in processed_df.columns:
                try:
                    y_true_text = processed_df['Label_Tag']
                    try:
                        # Attempt to transform actual labels
                        y_true_numeric = le.transform(y_true_text)
                        acc = accuracy_score(y_true_numeric, y_pred_numeric)
                        y_true_inversed = le.inverse_transform(y_true_numeric)
                        class_report = classification_report(y_true_inversed, predictions, zero_division=0)
                        cm = confusion_matrix(y_true_inversed, predictions, labels=le.classes_)

                        # Save to model_metrics
                        if not self.model_metrics:
                            self.model_metrics = {}
                        self.model_metrics['accuracy'] = acc
                        self.model_metrics['report'] = class_report
                        self.model_metrics['cm'] = cm
                        self.save_metrics_to_file(self.model_metrics)

                        # Enable show metrics button
                        self.master.after(0, lambda: self.show_metrics_button.config(state=tk.NORMAL))

                    except ValueError:
                        pass  # Possibly unseen labels

                except Exception:
                    pass

            # Ask user to save predictions
            save_path = filedialog.asksaveasfilename(
                title="Save Predictions",
                defaultextension=".csv",
                filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
            )
            if save_path:
                processed_df.to_csv(save_path, index=False)
                self.master.after(0, lambda: messagebox.showinfo("Success", f"Predictions saved to {save_path}"))
            else:
                self.master.after(0, lambda: messagebox.showinfo("Cancelled", "Save operation cancelled."))

            self.master.after(0, lambda: self.predict_progress_bar.configure(value=100))
            self.master.after(0, lambda: self.update_status("Prediction complete!"))

        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Prediction Error", f"Error during prediction: {e}"))
            self.master.after(0, lambda: self.update_status("Idle"))
        finally:
            # Wait a bit, then reset progress bar
            time.sleep(0.5)
            self.master.after(0, lambda: self.predict_progress_bar.configure(value=0))

    def predict_window_progress_callback(self, current, total):
        """
        Moves the prediction progress bar from 0 to 80% as windows are processed.
        """
        if total == 0:
            progress = 0
        else:
            progress = (current / total) * 80
        self.master.after(0, lambda: self.predict_progress_bar.configure(value=progress))

    ########################################################################
    # DISPLAY METRICS (FOR PREDICTIONS ONLY)
    ########################################################################
    def display_metrics(self):
        if not self.model_metrics:
            messagebox.showwarning("No Metrics", "No metrics found. Make a prediction first.")
            return

        acc = self.model_metrics.get('accuracy', None)
        class_report = self.model_metrics.get('report', None)
        cm = self.model_metrics.get('cm', None)

        # If no classification info, just show 'trained_on'
        if (acc is None) or (class_report is None) or (cm is None):
            trained_on = self.model_metrics.get('trained_on', "Unknown file")
            simple_message = f"Model was trained on: {trained_on}\nNo prediction metrics available."
            messagebox.showinfo("Metrics", simple_message)
            return

        # Show a popup with classification metrics
        self.show_results_popup(acc, class_report, cm, title="Prediction Metrics")

    def show_results_popup(self, accuracy, class_report, cm, title="Results"):
        popup = tk.Toplevel(self.master)
        popup.title(title)
        popup.geometry("800x600")
        txt = scrolledtext.ScrolledText(popup, width=100, height=30)
        txt.pack(padx=10, pady=10, fill="both", expand=True)

        trained_on_file = self.model_metrics.get('trained_on', "Unknown")
        txt.insert(tk.END, f"Model trained on: {trained_on_file}\n\n")
        txt.insert(tk.END, f"Accuracy: {accuracy:.4f}\n\n")
        txt.insert(tk.END, "Classification Report:\n")
        txt.insert(tk.END, class_report + "\n")
        txt.insert(tk.END, "Confusion Matrix:\n")
        txt.insert(tk.END, str(cm) + "\n")
        txt.config(state="disabled")

    ########################################################################
    # REAL-TIME PREDICTIONS
    ########################################################################
    def get_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def refresh_rt_ports(self):
        ports = self.get_serial_ports()
        menu = self.rt_port_dropdown["menu"]
        menu.delete(0, "end")
        for p in ports:
            menu.add_command(label=p, command=lambda val=p: self.rt_port_var.set(val))
        if ports:
            self.rt_port_var.set(ports[0])
        else:
            self.rt_port_var.set("")
        self.update_status(f"Ports refreshed. Available ports: {', '.join(ports) if ports else 'None'}")

    def rt_connect_serial(self):
        if not self.rt_port_var.get():
            self.update_status("No serial port selected for real-time predictions.")
            messagebox.showwarning("Warning", "No serial port selected for real-time predictions.")
            return
        try:
            self.rt_serial_port = serial.Serial(self.rt_port_var.get(), 115200, timeout=1)
            time.sleep(2)
            self.rt_connected = True
            self.update_status(f"Connected to {self.rt_port_var.get()} for real-time predictions.")
            self.rt_connect_button.config(state=tk.DISABLED)
            self.rt_disconnect_button.config(state=tk.NORMAL)
            self.rt_start_button.config(state=tk.NORMAL)
        except serial.SerialException as e:
            self.update_status(f"RT Connection Error: {str(e)}")
            messagebox.showerror("Connection Error", f"Failed to connect to {self.rt_port_var.get()}.\nError: {str(e)}")

    def rt_disconnect_serial(self):
        if self.rt_serial_port and self.rt_serial_port.is_open:
            if self.rt_logging:
                self.rt_stop_predictions()
            self.rt_stop_event.set()
            self.rt_serial_port.close()
            self.rt_connected = False
            self.update_status("RT serial port disconnected.")
            self.rt_connect_button.config(state=tk.NORMAL)
            self.rt_disconnect_button.config(state=tk.DISABLED)
            self.rt_start_button.config(state=tk.DISABLED)
            self.rt_stop_button.config(state=tk.DISABLED)

    def rt_start_predictions(self):
        if not self.rt_connected:
            messagebox.showwarning("Warning", "Not connected to any port.")
            return
        if not os.path.exists(self.model_path):
            messagebox.showwarning("Warning", "No trained model available. Train a model first.")
            return
        self.rt_send_command("START")
        self.rt_logging = True
        self.rt_stop_event.clear()
        self.rt_stop_button.config(state=tk.NORMAL)
        self.rt_start_button.config(state=tk.DISABLED)
        self.update_status("Real-time predictions started.")
        self.rt_data_buffer.clear()
        self.rt_data_display.config(state='normal')
        self.rt_data_display.delete('1.0', tk.END)
        self.rt_data_display.config(state='disabled')
        self.rt_read_thread = threading.Thread(target=self.rt_read_serial_data, daemon=True)
        self.rt_read_thread.start()

    def rt_stop_predictions(self):
        self.rt_logging = False
        self.rt_stop_event.set()
        self.rt_stop_button.config(state=tk.DISABLED)
        self.rt_start_button.config(state=tk.NORMAL)
        self.update_status("Real-time predictions stopped.")
        self.rt_send_command("STOP")

    def rt_send_command(self, command):
        if self.rt_serial_port and self.rt_serial_port.is_open:
            try:
                self.rt_serial_port.write(f"{command}\n".encode())
                self.update_status(f"Sent command: {command}")
            except serial.SerialException as e:
                self.update_status(f"Serial Communication Error: {str(e)}")
                messagebox.showerror("Communication Error", f"Failed to send command.\nError: {str(e)}")

    def rt_read_serial_data(self):
        buffer = ""
        start_time = None
        try:
            batch_length = float(self.batch_length_var.get())
        except ValueError:
            batch_length = 5  # fallback if user input is invalid

        processor = DataProcessor()
        selected_features = list(FEATURES.keys())

        columns = [
            "Real_Time",
            "Timestamp_ms",
            "Label_Tag",
            "HeaterProfile_ID",
            "Sensor1_Temperature_deg_C",
            "Sensor1_Pressure_Pa",
            "Sensor1_Humidity_%",
            "Sensor1_GasResistance_ohm",
            "Sensor1_Status",
            "Sensor1_GasIndex",
            "Sensor2_Temperature_deg_C",
            "Sensor2_Pressure_Pa",
            "Sensor2_Humidity_%",
            "Sensor2_GasResistance_ohm",
            "Sensor2_Status",
            "Sensor2_GasIndex",
            "Sensor3_Temperature_deg_C",
            "Sensor3_Pressure_Pa",
            "Sensor3_Humidity_%",
            "Sensor3_GasResistance_ohm",
            "Sensor3_Status",
            "Sensor3_GasIndex",
            "Sensor4_Temperature_deg_C",
            "Sensor4_Pressure_Pa",
            "Sensor4_Humidity_%",
            "Sensor4_GasResistance_ohm",
            "Sensor4_Status",
            "Sensor4_GasIndex",
            "Sensor5_Temperature_deg_C",
            "Sensor5_Pressure_Pa",
            "Sensor5_Humidity_%",
            "Sensor5_GasResistance_ohm",
            "Sensor5_Status",
            "Sensor5_GasIndex",
            "Sensor6_Temperature_deg_C",
            "Sensor6_Pressure_Pa",
            "Sensor6_Humidity_%",
            "Sensor6_GasResistance_ohm",
            "Sensor6_Status",
            "Sensor6_GasIndex",
            "Sensor7_Temperature_deg_C",
            "Sensor7_Pressure_Pa",
            "Sensor7_Humidity_%",
            "Sensor7_GasResistance_ohm",
            "Sensor7_Status",
            "Sensor7_GasIndex",
            "Sensor8_Temperature_deg_C",
            "Sensor8_Pressure_Pa",
            "Sensor8_Humidity_%",
            "Sensor8_GasResistance_ohm",
            "Sensor8_Status",
            "Sensor8_GasIndex"
        ]
        expected_col_count = len(columns)
        non_numeric_cols = ["Real_Time", "Label_Tag", "HeaterProfile_ID"]
        for sn in range(1, 9):
            non_numeric_cols.append(f"Sensor{sn}_Status")
        numeric_cols = [c for c in columns if c not in non_numeric_cols]

        try:
            clf, le = load(self.model_path)
        except:
            self.update_status("No model file found for real-time predictions.")
            return

        while not self.rt_stop_event.is_set():
            if self.rt_serial_port and self.rt_serial_port.in_waiting > 0:
                try:
                    byte_data = self.rt_serial_port.read(self.rt_serial_port.in_waiting)
                    buffer += byte_data.decode(errors='ignore')

                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if not line:
                            continue

                        # Show raw data in the UI console
                        self.rt_data_display.config(state='normal')
                        self.rt_data_display.insert(tk.END, line + "\n")
                        self.rt_data_display.yview(tk.END)
                        self.rt_data_display.config(state='disabled')

                        csv_reader = csv.reader(StringIO(line))
                        parsed = next(csv_reader, None)
                        if not parsed:
                            continue

                        # If Real_Time is missing, prepend it
                        if len(parsed) == expected_col_count - 1:
                            real_time_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                            parsed = [real_time_str] + parsed
                        elif len(parsed) != expected_col_count:
                            continue

                        # Convert to DataFrame row
                        try:
                            row_df = pd.DataFrame([parsed], columns=columns)
                            for col in numeric_cols:
                                row_df[col] = pd.to_numeric(row_df[col], errors='coerce')
                        except:
                            continue

                        self.rt_data_buffer.append(row_df)

                        # Initialize timer
                        if start_time is None:
                            start_time = time.time()

                        elapsed = time.time() - start_time
                        remain = max(0, round(batch_length - elapsed))
                        self.time_left_var.set(str(remain))

                        # Once we hit batch_length seconds, process
                        if elapsed >= batch_length:
                            batch_df = pd.concat(self.rt_data_buffer, ignore_index=True)
                            self.rt_data_buffer.clear()
                            start_time = time.time()
                            self.time_left_var.set(str(int(batch_length)))

                            try:
                                # Use process_batch with window=5, stride=1 (or your set values)
                                features_df = processor.process_batch(
                                    batch_df,
                                    window_size=WINDOW_SIZE,
                                    stride=STRIDE,
                                    selected_features=selected_features
                                )

                                if not features_df.empty:
                                    # Remove 'Real_Time'/'Label_Tag' so columns match training
                                    feature_cols_batch = [
                                        c for c in features_df.columns
                                        if c not in ['Label_Tag', 'Real_Time']
                                    ]
                                    preds_numeric = clf.predict(features_df[feature_cols_batch])
                                    # Transform numeric predictions to label names
                                    final_pred_list = le.inverse_transform(preds_numeric)

                                    # Determine the top two predictions (or only one if unique)
                                    if len(final_pred_list) == 0:
                                        self.current_prediction.set("No features extracted")
                                    else:
                                        # Count how many times each label appears
                                        values, counts = np.unique(final_pred_list, return_counts=True)
                                        sorted_indices = np.argsort(counts)[::-1]

                                        if len(sorted_indices) == 1:
                                            # Only one label predicted in all windows
                                            single_label = values[sorted_indices[0]]
                                            self.current_prediction.set(
                                                f"Single label: {single_label}"
                                            )
                                        else:
                                            # Top two labels
                                            top_label_1 = values[sorted_indices[0]]
                                            top_label_2 = values[sorted_indices[1]]
                                            top_count_1 = counts[sorted_indices[0]]
                                            top_count_2 = counts[sorted_indices[1]]
                                            total_count = len(final_pred_list)

                                            percentage_1 = 100.0 * top_count_1 / total_count
                                            percentage_2 = 100.0 * top_count_2 / total_count

                                            pred_text = (
                                                f"Between {top_label_1} "
                                                f"({percentage_1:.1f}%) and {top_label_2} "
                                                f"({percentage_2:.1f}%) - "
                                                f"Likely: {top_label_1}"
                                            )
                                            self.current_prediction.set(pred_text)
                                else:
                                    self.current_prediction.set("No features extracted")

                            except Exception as ex:
                                import traceback
                                traceback.print_exc()
                                self.update_status(f"Batch processing error: {ex}")

                except serial.SerialException:
                    self.update_status("Serial Communication Error: Connection lost.")
                    messagebox.showerror("Communication Error", "Serial Communication Error: Connection lost.")
                    break

    ########################################################################
    # STATUS & MAINLOOP
    ########################################################################
    def update_status(self, message):
        self.status.set(message)

    def mainloop(self):
        self.master.mainloop()

def main():
    root = tk.Tk()
    app = ModelTrainerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

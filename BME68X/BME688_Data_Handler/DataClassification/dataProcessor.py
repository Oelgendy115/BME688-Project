# Import necessary libraries for data processing and GUI dialogs
import numpy as np
import pandas as pd
import os
import tkinter as tk
from tkinter import simpledialog

# Define the file path for the label encoder CSV that maps raw labels to class names.
LABEL_ENCODER_PATH = "BME68X/BME688_Data_Handler/Label_Encoder.csv"

def make_feature_func(column, func):
    """
    Creates and returns a function that computes a statistic on a specific DataFrame column.
    The returned function applies the provided statistical function to the column data,
    rounding the result if it's a floating point value, and returns NaN if an error occurs.
    """
    def feature_func(batch):
        try:
            result = func(batch[column])
            if isinstance(result, (float, np.floating)):
                return round(result, 2)
            return result
        except Exception:
            return np.nan
    return feature_func

def get_feature_functions(data_interval=3, sensor_count=8):
    """
    Dynamically generates a dictionary of feature extraction functions for multiple sensors.
    For each sensor and each measurement type (GasResistance, Temperature, Pressure, Humidity),
    functions to compute mean, standard deviation, minimum, and maximum are created.

    Parameters:
      data_interval: Interval between data points in seconds (not used in the computation).
      sensor_count: Number of sensors to process.

    Returns:
      A dictionary where keys are feature names and values are functions that take a DataFrame
      window and return the computed statistic.
    """
    features = {}
    # Map each measurement type to its column suffix and associated statistical functions.
    measurement_map = {
        "GasResistance": ("GasResistance_ohm", np.mean, np.std, np.min, np.max),
        "Temperature":   ("Temperature_deg_C", np.mean, np.std, np.min, np.max),
        "Pressure":      ("Pressure_Pa", np.mean, np.std, np.min, np.max),
        "Humidity":      ("Humidity_%", np.mean, np.std, np.min, np.max)
    }
    # For each sensor and measurement, create a feature function for mean, standard deviation, min, and max.
    for sensor_num in range(1, sensor_count + 1):
        for measurement, (col_suffix, mean_func, std_func, min_func, max_func) in measurement_map.items():
            funcs = {"Mean": mean_func, "StdDev": std_func, "Min": min_func, "Max": max_func}
            for stat, func in funcs.items():
                col_name = f"Sensor{sensor_num}_{col_suffix}"
                feature_name = f"{measurement}_{stat}_Sensor{sensor_num}"
                features[feature_name] = make_feature_func(col_name, func)
    return features

class DataProcessor:
    """
    A class for processing sensor data, including reading CSV files, validating columns,
    extracting features from sliding time windows, managing label encoding, and saving results.
    """
    def __init__(self, label_encoder_path=LABEL_ENCODER_PATH, features=None, sensor_count=8, data_interval=3):
        """
        Initializes the DataProcessor with configuration settings, label encoding, and feature functions.

        Parameters:
          label_encoder_path: Path to the CSV file for label encoding.
          features: Optional dictionary of feature functions; if not provided, defaults are generated.
          sensor_count: Total number of sensors.
          data_interval: Expected interval (in seconds) between data samples.
        """
        self.output_data = []
        self.label_encoder_path = label_encoder_path
        self.label_mapping = self.load_label_encoder(self.label_encoder_path)
        self.sensor_count = sensor_count
        self.data_interval = data_interval
        self.features = features if features is not None else get_feature_functions(data_interval, sensor_count)
    
    def load_label_encoder(self, path):
        """
        Loads the label encoder from a CSV file and creates a dictionary mapping raw labels to class names.

        Parameters:
          path: File path to the CSV label encoder.

        Returns:
          A dictionary with raw label keys and their corresponding class name values.
        """
        label_dict = {}
        if not os.path.isfile(path):
            print(f"Label encoder file not found: {path} -- will create one on new label.")
            return label_dict

        try:
            df_encoder = pd.read_csv(path)
            for _, row in df_encoder.iterrows():
                raw_tag = row['Label_Tag']
                class_name = row['Class_name']
                try:
                    raw_tag = int(float(raw_tag))
                except ValueError:
                    pass
                label_dict[raw_tag] = str(class_name)
        except Exception as e:
            print(f"Could not load label encoder from {path}: {e}")
        return label_dict

    def update_label_encoder(self, raw_label, new_class_name):
        """
        Appends a new raw label-to-class name mapping to the label encoder CSV file and updates
        the in-memory dictionary.

        Parameters:
          raw_label: The raw label encountered in the data.
          new_class_name: The new class name provided by the user.
        """
        self.label_mapping[raw_label] = new_class_name
        file_exists = os.path.isfile(self.label_encoder_path)
        mode = 'a' if file_exists else 'w'
        with open(self.label_encoder_path, mode, newline='') as f:
            if not file_exists:
                f.write("Label_Tag,Class_name\n")
            f.write(f"{raw_label},{new_class_name}\n")

    def ask_for_new_label_name(self, raw_label):
        """
        Displays a GUI dialog box to prompt the user to assign a new class name for an unknown label.
        If the user cancels or provides no input, the raw label is used as the class name.

        Parameters:
          raw_label: The raw label that requires a human-readable class name.

        Returns:
          The class name provided by the user or the string representation of the raw label.
        """
        import threading
        parent = tk._default_root if tk._default_root is not None else None
        if parent:
            parent.update_idletasks()
        prompt_text = (
            f"A new label '{raw_label}' was encountered.\n"
            "Please enter a class name for this label, or click Cancel to keep the numeric/string value."
        )
        result = [None]
        event = threading.Event()

        def ask_dialog():
            try:
                user_input = simpledialog.askstring("New Label Encountered", prompt_text, parent=parent)
            except Exception:
                user_input = None
            result[0] = user_input if user_input else str(raw_label)
            event.set()

        if parent:
            parent.after(0, ask_dialog)
        else:
            ask_dialog()

        event.wait()
        self.update_label_encoder(raw_label, result[0])
        return result[0]

    def read_csv(self, input_file):
        """
        Reads sensor data from a CSV file into a pandas DataFrame.

        Parameters:
          input_file: The path to the input CSV file.

        Returns:
          A DataFrame containing the sensor data.

        Raises:
          FileNotFoundError: If the CSV file does not exist.
          Exception: If an error occurs during CSV reading.
        """
        if not os.path.isfile(input_file):
            raise FileNotFoundError(f"Input CSV not found: {input_file}")
        try:
            df = pd.read_csv(input_file)
            print(f"Read {len(df)} rows from {input_file}")
            return df
        except Exception as e:
            raise Exception(f"Error reading CSV file: {e}")

    def check_required_columns(self, df):
        """
        Verifies that the DataFrame contains all mandatory columns, including general metadata
        and sensor-specific measurements.

        Parameters:
          df: The DataFrame to validate.

        Raises:
          Exception: If any required columns are missing.
        """
        required_columns = [
            'Real_Time', 'Timestamp_ms', 'Label_Tag', 'HeaterProfile_ID',
        ]
        for sensor_num in range(1, self.sensor_count + 1):
            required_columns.extend([
                f'Sensor{sensor_num}_Temperature_deg_C',
                f'Sensor{sensor_num}_Pressure_Pa',
                f'Sensor{sensor_num}_Humidity_%',
                f'Sensor{sensor_num}_GasResistance_ohm',
                f'Sensor{sensor_num}_Status',
                f'Sensor{sensor_num}_GasIndex',
            ])
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise Exception(f"Missing columns in CSV: {missing_columns}")

    def process_data(self, df, window_size, stride, selected_features, data_interval=None, gap_threshold=None, progress_callback=None):
        """
        Processes the sensor data by dividing it into sliding time windows, computing features
        for each window, and assigning human-readable class names to labels. It handles gaps in
        the data, validates window completeness, and optionally tracks processing progress.

        Parameters:
          df: The DataFrame containing the sensor data.
          window_size: The duration (in seconds) of each sliding window.
          stride: The step (in seconds) by which the window moves.
          selected_features: A list of feature names to compute.
          data_interval: Optional expected interval between data points.
          gap_threshold: Optional maximum gap (in seconds) allowed to consider data continuous.
          progress_callback: Optional callback function for progress updates.

        Returns:
          A list of dictionaries, each representing computed features and metadata for a window.
        """
        self.check_required_columns(df)
        df['Real_Time'] = pd.to_datetime(df['Real_Time'], errors='coerce')
        df = df.sort_values('Real_Time').reset_index(drop=True)
        if df['Real_Time'].isnull().all():
            raise Exception("All 'Real_Time' entries are NaT. Cannot proceed.")

        current_data_interval = data_interval if data_interval is not None else self.data_interval
        gap_threshold = pd.Timedelta(seconds=current_data_interval * 3) if gap_threshold is None else pd.Timedelta(seconds=gap_threshold)
        window_size_td = pd.Timedelta(seconds=window_size)
        stride_td = pd.Timedelta(seconds=stride)

        # Mark gaps in time series data and assign block IDs for continuous segments.
        df['Time_Diff'] = df['Real_Time'].diff()
        df['Block_ID'] = (df['Time_Diff'] > gap_threshold).cumsum()

        # Estimate the total number of windows for optional progress reporting.
        total_windows = 0
        for _, block_df in df.groupby('Block_ID'):
            block_start = block_df['Real_Time'].iloc[0]
            block_end = block_df['Real_Time'].iloc[-1]
            window_start = block_start
            while window_start + window_size_td <= block_end:
                total_windows += 1
                window_start += stride_td

        output_data = []
        windows_processed = 0

        # Process each continuous block of data.
        for _, block_df in df.groupby('Block_ID'):
            block_start = block_df['Real_Time'].iloc[0]
            block_end = block_df['Real_Time'].iloc[-1]
            window_start = block_start

            while window_start + window_size_td <= block_end:
                window_end = window_start + window_size_td
                window_df = block_df[(block_df['Real_Time'] >= window_start) & (block_df['Real_Time'] < window_end)]
                # Skip windows that are empty or have inconsistent labels.
                if window_df.empty or window_df['Label_Tag'].nunique() != 1:
                    window_start += stride_td
                    windows_processed += 1
                    if progress_callback:
                        progress_callback(windows_processed, total_windows)
                    continue

                # Ensure the window covers a sufficient portion of the expected duration.
                actual_duration = (window_df['Real_Time'].iloc[-1] - window_df['Real_Time'].iloc[0]).total_seconds()
                if actual_duration < window_size * 0.8:
                    window_start += stride_td
                    windows_processed += 1
                    if progress_callback:
                        progress_callback(windows_processed, total_windows)
                    continue

                # Process the label: attempt to convert to integer, otherwise use as string.
                raw_label_str = str(window_df['Label_Tag'].iloc[-1]).strip()
                try:
                    raw_label = int(float(raw_label_str))
                except ValueError:
                    raw_label = raw_label_str

                # If the raw label is new, prompt the user to assign a class name.
                if raw_label not in self.label_mapping:
                    class_name = self.ask_for_new_label_name(raw_label)
                else:
                    class_name = self.label_mapping[raw_label]

                # Compute the selected features for the current window.
                features = self.calculate_features(window_df, selected_features)
                features['Real_Time'] = window_df['Real_Time'].iloc[0]
                features['Label_Tag'] = class_name
                output_data.append(features)

                window_start += stride_td
                windows_processed += 1
                if progress_callback:
                    progress_callback(windows_processed, total_windows)

        self.output_data = output_data
        return output_data

    def process_batch(self, batch_df, window_size, stride, selected_features, data_interval=None, gap_threshold=None):
        """
        Processes a batch of sensor data similar to process_data but returns the result as a DataFrame.
        It divides the data into sliding windows, computes the selected features, and assigns proper labels.

        Parameters:
          batch_df: The DataFrame containing the sensor data.
          window_size: Duration (in seconds) of each sliding window.
          stride: Step (in seconds) by which the window slides.
          selected_features: List of features to compute.
          data_interval: Optional expected interval between data points.
          gap_threshold: Optional maximum gap (in seconds) to treat data as continuous.

        Returns:
          A DataFrame with computed features and metadata for each valid window.
        """
        self.check_required_columns(batch_df)
        batch_df['Real_Time'] = pd.to_datetime(batch_df['Real_Time'], errors='coerce')
        batch_df = batch_df.sort_values('Real_Time').reset_index(drop=True)
        if batch_df['Real_Time'].isnull().all():
            raise Exception("All 'Real_Time' entries are NaT. Cannot proceed.")

        current_data_interval = data_interval if data_interval is not None else self.data_interval
        gap_threshold = pd.Timedelta(seconds=current_data_interval * 3) if gap_threshold is None else pd.Timedelta(seconds=gap_threshold)
        window_size_td = pd.Timedelta(seconds=window_size)
        stride_td = pd.Timedelta(seconds=stride)

        batch_df['Time_Diff'] = batch_df['Real_Time'].diff()
        batch_df['Block_ID'] = (batch_df['Time_Diff'] > gap_threshold).cumsum()

        output_data = []
        # Process each continuous segment in the batch.
        for _, block_df in batch_df.groupby('Block_ID'):
            block_start = block_df['Real_Time'].iloc[0]
            block_end = block_df['Real_Time'].iloc[-1]
            window_start = block_start

            while window_start + window_size_td <= block_end:
                window_end = window_start + window_size_td
                window_df = block_df[(block_df['Real_Time'] >= window_start) & (block_df['Real_Time'] < window_end)]
                if window_df.empty or window_df['Label_Tag'].nunique() != 1:
                    window_start += stride_td
                    continue

                actual_duration = (window_df['Real_Time'].iloc[-1] - window_df['Real_Time'].iloc[0]).total_seconds()
                if actual_duration < window_size * 0.8:
                    window_start += stride_td
                    continue

                raw_label_str = str(window_df['Label_Tag'].iloc[-1]).strip()
                try:
                    raw_label = int(float(raw_label_str))
                except ValueError:
                    raw_label = raw_label_str

                if raw_label not in self.label_mapping:
                    class_name = self.ask_for_new_label_name(raw_label)
                else:
                    class_name = self.label_mapping[raw_label]

                features = self.calculate_features(window_df, selected_features)
                features['Real_Time'] = window_df['Real_Time'].iloc[0]
                features['Label_Tag'] = class_name
                output_data.append(features)
                window_start += stride_td

        if output_data:
            df_out = pd.DataFrame(output_data).round(2)
            if 'Real_Time' in df_out.columns:
                cols = df_out.columns.tolist()
                cols.remove('Real_Time')
                df_out = df_out[['Real_Time'] + cols]
            return df_out
        else:
            return pd.DataFrame()

    def calculate_features(self, window_df, selected_features):
        """
        Computes and returns the selected features for a given window of sensor data using the
        pre-defined feature functions.

        Parameters:
          window_df: The DataFrame corresponding to a time window of sensor data.
          selected_features: List of feature names to calculate.

        Returns:
          A dictionary mapping each feature name to its computed value.
        """
        features = {}
        for feature_name in selected_features:
            feature_func = self.features.get(feature_name)
            if feature_func:
                try:
                    value = feature_func(window_df)
                    features[feature_name] = value
                except Exception:
                    features[feature_name] = np.nan
        return features

    def save_output(self, output_data, output_path):
        """
        Saves the processed sensor data with computed features to a CSV file.

        Parameters:
          output_data: List of dictionaries containing processed window data.
          output_path: File path where the output CSV should be saved.
        """
        try:
            output_df = pd.DataFrame(output_data).round(2)
            if 'Real_Time' in output_df.columns:
                cols = output_df.columns.tolist()
                cols.remove('Real_Time')
                output_df = output_df[['Real_Time'] + cols]
            output_df.to_csv(output_path, index=False, float_format='%.2f')
            print(f"Output saved to {output_path}")
        except Exception as e:
            print(f"Error saving output CSV: {e}")

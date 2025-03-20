# dataProcessor.py

import numpy as np
import pandas as pd
from scipy.fft import fft, fftfreq
from scipy.stats import entropy

def calculate_gasresistance_mean(batch, sensor_number):
    column = f'Sensor{sensor_number}_GasResistance_ohm'
    return batch[column].mean()

def calculate_gasresistance_std(batch, sensor_number):
    column = f'Sensor{sensor_number}_GasResistance_ohm'
    return batch[column].std()

def calculate_gasresistance_min(batch, sensor_number):
    column = f'Sensor{sensor_number}_GasResistance_ohm'
    return batch[column].min()

def calculate_gasresistance_max(batch, sensor_number):
    column = f'Sensor{sensor_number}_GasResistance_ohm'
    return batch[column].max()

def calculate_temperature_mean(batch, sensor_number):
    column = f'Sensor{sensor_number}_Temperature_deg_C'
    return batch[column].mean()

def calculate_temperature_std(batch, sensor_number):
    column = f'Sensor{sensor_number}_Temperature_deg_C'
    return batch[column].std()

def calculate_temperature_min(batch, sensor_number):
    column = f'Sensor{sensor_number}_Temperature_deg_C'
    return batch[column].min()

def calculate_temperature_max(batch, sensor_number):
    column = f'Sensor{sensor_number}_Temperature_deg_C'
    return batch[column].max()

def calculate_pressure_mean(batch, sensor_number):
    column = f'Sensor{sensor_number}_Pressure_Pa'
    return batch[column].mean()

def calculate_pressure_std(batch, sensor_number):
    column = f'Sensor{sensor_number}_Pressure_Pa'
    return batch[column].std()

def calculate_pressure_min(batch, sensor_number):
    column = f'Sensor{sensor_number}_Pressure_Pa'
    return batch[column].min()

def calculate_pressure_max(batch, sensor_number):
    column = f'Sensor{sensor_number}_Pressure_Pa'
    return batch[column].max()

def calculate_humidity_mean(batch, sensor_number):
    column = f'Sensor{sensor_number}_Humidity_%'
    return batch[column].mean()

def calculate_humidity_std(batch, sensor_number):
    column = f'Sensor{sensor_number}_Humidity_%'
    return batch[column].std()

def calculate_humidity_min(batch, sensor_number):
    column = f'Sensor{sensor_number}_Humidity_%'
    return batch[column].min()

def calculate_humidity_max(batch, sensor_number):
    column = f'Sensor{sensor_number}_Humidity_%'
    return batch[column].max()

def get_feature_functions(sampling_rate=10.0):
    features = {}
    for sensor_num in range(1, 9):
        features[f'GasResistance_Mean_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_gasresistance_mean(batch, sn)
        features[f'GasResistance_StdDev_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_gasresistance_std(batch, sn)
        features[f'GasResistance_Min_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_gasresistance_min(batch, sn)
        features[f'GasResistance_Max_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_gasresistance_max(batch, sn)
    for sensor_num in range(1, 9):
        features[f'Temperature_Mean_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_temperature_mean(batch, sn)
        features[f'Temperature_StdDev_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_temperature_std(batch, sn)
        features[f'Temperature_Min_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_temperature_min(batch, sn)
        features[f'Temperature_Max_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_temperature_max(batch, sn)
    for sensor_num in range(1, 9):
        features[f'Pressure_Mean_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_pressure_mean(batch, sn)
        features[f'Pressure_StdDev_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_pressure_std(batch, sn)
        features[f'Pressure_Min_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_pressure_min(batch, sn)
        features[f'Pressure_Max_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_pressure_max(batch, sn)
    for sensor_num in range(1, 9):
        features[f'Humidity_Mean_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_humidity_mean(batch, sn)
        features[f'Humidity_StdDev_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_humidity_std(batch, sn)
        features[f'Humidity_Min_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_humidity_min(batch, sn)
        features[f'Humidity_Max_Sensor{sensor_num}'] = lambda batch, sn=sensor_num: calculate_humidity_max(batch, sn)
    return features

FEATURES = get_feature_functions(sampling_rate=10.0)

class DataProcessor:
    def __init__(self):
        self.output_data = []

    def read_csv(self, input_file):
        try:
            df = pd.read_csv(input_file)
            print(f"Read {len(df)} rows from {input_file}")
            return df
        except Exception as e:
            raise Exception(f"Error reading CSV file: {e}")

    def check_required_columns(self, df):
        required_columns = [
            'Real_Time', 'Timestamp_ms', 'Label_Tag', 'HeaterProfile_ID',
        ]
        for sensor_num in range(1, 9):
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

    def process_data(self, df, window_size, stride, selected_features, progress_callback=None):
        self.check_required_columns(df)
        df['Real_Time'] = pd.to_datetime(df['Real_Time'], errors='coerce')
        df = df.sort_values('Real_Time').reset_index(drop=True)
        if df['Real_Time'].isnull().all():
            raise Exception("All 'Real_Time' entries are NaT. Cannot proceed.")
        window_size_td = pd.Timedelta(seconds=window_size)
        stride_td = pd.Timedelta(seconds=stride)
        df['Time_Diff'] = df['Real_Time'].diff()
        threshold = pd.Timedelta(seconds=10)
        df['Block_ID'] = (df['Time_Diff'] > threshold).cumsum()
        output_data = []
        total_windows = 0
        for block_id, block_df in df.groupby('Block_ID'):
            block_start = block_df['Real_Time'].iloc[0]
            block_end = block_df['Real_Time'].iloc[-1]
            window_start = block_start
            while window_start + window_size_td <= block_end:
                total_windows += 1
                window_start += stride_td
        windows_processed = 0
        for block_id, block_df in df.groupby('Block_ID'):
            block_start = block_df['Real_Time'].iloc[0]
            block_end = block_df['Real_Time'].iloc[-1]
            window_start = block_start
            while window_start + window_size_td <= block_end:
                window_end = window_start + window_size_td
                window_df = block_df[
                    (block_df['Real_Time'] >= window_start) &
                    (block_df['Real_Time'] < window_end)
                ]
                if not window_df.empty:
                    features = self.calculate_features(window_df, selected_features)
                    features['Label_Tag'] = window_df['Label_Tag'].iloc[-1]
                    output_data.append(features)
                windows_processed += 1
                if progress_callback:
                    progress_callback(windows_processed, total_windows)
                window_start += stride_td
        self.output_data = output_data
        return output_data

    def process_batch(self, batch_df, window_size, stride, selected_features):
        if not isinstance(batch_df, pd.DataFrame):
            raise ValueError("Input batch must be a pandas DataFrame.")
        self.check_required_columns(batch_df)
        batch_df['Real_Time'] = pd.to_datetime(batch_df['Real_Time'], errors='coerce')
        batch_df = batch_df.sort_values('Real_Time').reset_index(drop=True)
        if batch_df['Real_Time'].isnull().all():
            raise Exception("All 'Real_Time' entries are NaT. Cannot proceed.")
        window_size_td = pd.Timedelta(seconds=window_size)
        stride_td = pd.Timedelta(seconds=stride)
        batch_df['Time_Diff'] = batch_df['Real_Time'].diff()
        threshold = pd.Timedelta(seconds=10)
        batch_df['Block_ID'] = (batch_df['Time_Diff'] > threshold).cumsum()
        output_data = []
        total_windows = 0
        for block_id, block_df2 in batch_df.groupby('Block_ID'):
            block_start = block_df2['Real_Time'].iloc[0]
            block_end = block_df2['Real_Time'].iloc[-1]
            window_start = block_start
            while window_start + window_size_td <= block_end:
                total_windows += 1
                window_start += stride_td
        windows_processed = 0
        for block_id, block_df2 in batch_df.groupby('Block_ID'):
            block_start = block_df2['Real_Time'].iloc[0]
            block_end = block_df2['Real_Time'].iloc[-1]
            window_start = block_start
            while window_start + window_size_td <= block_end:
                window_end = window_start + window_size_td
                window_df = block_df2[
                    (block_df2['Real_Time'] >= window_start) &
                    (block_df2['Real_Time'] < window_end)
                ]
                if not window_df.empty:
                    features = self.calculate_features(window_df, selected_features)
                    if 'Label_Tag' in window_df.columns:
                        features['Label_Tag'] = window_df['Label_Tag'].iloc[-1]
                    output_data.append(features)
                windows_processed += 1
                window_start += stride_td
        if output_data:
            return pd.DataFrame(output_data).round(2)
        else:
            return pd.DataFrame()

    def calculate_features(self, window_df, selected_features):
        features = {}
        for feature_name in selected_features:
            feature_func = FEATURES.get(feature_name)
            if feature_func:
                try:
                    value = feature_func(window_df)
                    if isinstance(value, float):
                        value = round(value, 2)
                    features[feature_name] = value
                except Exception:
                    features[feature_name] = np.nan
        return features

    def save_output(self, output_data, output_path):
        try:
            output_df = pd.DataFrame(output_data)
            output_df = output_df.round(2)
            output_df.to_csv(output_path, index=False, float_format='%.2f')
        except Exception as e:
            print(f"Error saving output CSV: {e}")

def main():
    input_path = "Coffee_Air_test.csv"
    output_path = "testingChips_30.csv"
    window_size = 5
    stride = 1
    processor = DataProcessor()
    try:
        df = processor.read_csv(input_path)
        selected_features = list(FEATURES.keys())
        processed_data = processor.process_data(df, window_size, stride, selected_features)
        processor.save_output(processed_data, output_path)
    except Exception as e:
        print(f"An error occurred during data processing: {e}")

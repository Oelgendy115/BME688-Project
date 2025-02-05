# tests/test_dataProcessor.py

import pytest
import pandas as pd
import numpy as np
import os
from dataProcessor import DataProcessor, FEATURES

@pytest.fixture
def sample_dataframe():
    """Fixture to create a sample DataFrame with all required columns."""
    data = {
        'Real_Time': pd.date_range(start='2023-01-01', periods=10, freq='S'),
        'Timestamp_ms': np.arange(10) * 1000,
        'Label_Tag': ['A'] * 10,
        'HeaterProfile_ID': [1] * 10,
    }
    for sensor_num in range(1, 9):
        data[f'Sensor{sensor_num}_Temperature_deg_C'] = np.random.uniform(20, 30, 10)
        data[f'Sensor{sensor_num}_Pressure_Pa'] = np.random.uniform(1000, 1020, 10)
        data[f'Sensor{sensor_num}_Humidity_%'] = np.random.uniform(30, 50, 10)
        data[f'Sensor{sensor_num}_GasResistance_ohm'] = np.random.uniform(1e3, 1e4, 10)
        data[f'Sensor{sensor_num}_Status'] = ['OK'] * 10
        data[f'Sensor{sensor_num}_GasIndex'] = [0] * 10
    df = pd.DataFrame(data)
    return df

@pytest.fixture
def processor():
    """Fixture to create a DataProcessor instance."""
    return DataProcessor()

def test_read_csv_valid_file(tmp_path, processor):
    """Test reading a valid CSV file."""
    test_file = tmp_path / "test_valid.csv"
    sample_df = pd.DataFrame({
        'Real_Time': pd.date_range(start='2023-01-01', periods=5, freq='S'),
        'Timestamp_ms': [1000, 2000, 3000, 4000, 5000],
        'Label_Tag': ['A', 'B', 'C', 'D', 'E'],
        'HeaterProfile_ID': [1, 2, 3, 4, 5],
    })
    # Add sensor data
    for sensor_num in range(1, 9):
        sample_df[f'Sensor{sensor_num}_Temperature_deg_C'] = np.random.uniform(20, 30, 5)
        sample_df[f'Sensor{sensor_num}_Pressure_Pa'] = np.random.uniform(1000, 1020, 5)
        sample_df[f'Sensor{sensor_num}_Humidity_%'] = np.random.uniform(30, 50, 5)
        sample_df[f'Sensor{sensor_num}_GasResistance_ohm'] = np.random.uniform(1e3, 1e4, 5)
        sample_df[f'Sensor{sensor_num}_Status'] = ['OK'] * 5
        sample_df[f'Sensor{sensor_num}_GasIndex'] = [0] * 5
    sample_df.to_csv(test_file, index=False)
    
    df_read = processor.read_csv(test_file)
    assert len(df_read) == 5
    assert list(df_read.columns) == list(sample_df.columns)

def test_read_csv_invalid_file(processor):
    """Test reading a non-existent CSV file."""
    with pytest.raises(Exception) as exc_info:
        processor.read_csv("non_existent_file.csv")
    assert "Error reading CSV file" in str(exc_info.value)

def test_check_required_columns_present(processor, sample_dataframe):
    """Test that no exception is raised when all required columns are present."""
    try:
        processor.check_required_columns(sample_dataframe)
    except Exception as e:
        pytest.fail(f"check_required_columns raised an exception unexpectedly: {e}")

def test_check_required_columns_missing(processor, sample_dataframe):
    """Test that an exception is raised when required columns are missing."""
    df_missing = sample_dataframe.drop(columns=['Sensor1_Temperature_deg_C'])
    with pytest.raises(Exception) as exc_info:
        processor.check_required_columns(df_missing)
    assert "Missing columns in CSV" in str(exc_info.value)

def test_process_data(processor, sample_dataframe):
    """Test processing data with valid input."""
    selected_features = list(FEATURES.keys())
    output = processor.process_data(
        sample_dataframe, window_size=5, stride=1, selected_features=selected_features
    )
    assert isinstance(output, list)
    assert len(output) > 0
    assert 'Label_Tag' in output[0]

def test_process_data_invalid_time(processor, sample_dataframe):
    """Test processing data with invalid 'Real_Time' entries."""
    df_invalid_time = sample_dataframe.copy()
    df_invalid_time['Real_Time'] = pd.NaT
    with pytest.raises(Exception) as exc_info:
        processor.process_data(
            df_invalid_time, window_size=5, stride=1, selected_features=list(FEATURES.keys())
        )
    assert "All 'Real_Time' entries are NaT" in str(exc_info.value)

def test_save_output(processor, sample_dataframe, tmp_path):
    """Test saving processed data to CSV."""
    selected_features = list(FEATURES.keys())
    processed_data = processor.process_data(
        sample_dataframe, window_size=5, stride=1, selected_features=selected_features
    )
    output_path = tmp_path / "test_processed_features.csv"
    processor.save_output(processed_data, output_path)
    assert os.path.exists(output_path)
    df_saved = pd.read_csv(output_path)
    assert not df_saved.empty

def test_calculate_features(processor, sample_dataframe):
    """Test feature calculation."""
    window_df = sample_dataframe.iloc[0:5]
    selected_features = [
        'GasResistance_Mean_Sensor1',
        'Temperature_Mean_Sensor1',
        'Pressure_Mean_Sensor1',
        'Humidity_Mean_Sensor1'
    ]
    features = processor.calculate_features(window_df, selected_features)
    for feature in selected_features:
        assert feature in features
        assert isinstance(features[feature], float)

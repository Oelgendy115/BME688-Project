import pandas as pd
from bsec_interface import BSECWrapper

# Path to your raw CSV file
input_file = "raw_sensor_data.csv"
df = pd.read_csv(input_file)

# Create an instance of the BSEC wrapper
bsec = BSECWrapper()

# Prepare a list to collect BSEC outputs for each row
results = []

# Process each row using sensor 1 data (adjust the column names if needed)
for index, row in df.iterrows():
    temperature = row['Sensor1_Temperature_deg_C']
    pressure = row['Sensor1_Pressure_Pa']
    humidity = row['Sensor1_Humidity_%']
    gas_resistance = row['Sensor1_GasResistance_ohm']
    timestamp = int(row['Timestamp_ms'])  # ensure timestamp is an integer

    try:
        output = bsec.process_sensor_data(temperature, humidity, pressure, gas_resistance, timestamp)
    except Exception as e:
        print(f"Error processing row {index}: {e}")
        output = [-1, -1, -1, -1, -1]
    results.append(output)

# Convert the results to a DataFrame
results_df = pd.DataFrame(results, columns=[
    'IAQ', 'Static_IAQ', 'CO2_Equivalent', 'Breath_VOC_Equivalent', 'Accuracy'
])

# Concatenate the original DataFrame with the new columns
final_df = pd.concat([df, results_df], axis=1)

# Save the output to a new CSV file
output_file = "processed_sensor_data.csv"
final_df.to_csv(output_file, index=False)
print(f"Processing complete. Output saved to {output_file}")

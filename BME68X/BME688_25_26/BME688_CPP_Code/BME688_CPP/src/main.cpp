#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <bsec2.h>
#include <commMux/commMux.h>

/* Number of BME688 sensors connected through the multiplexer on the development kit */
#define NUM_OF_SENS 8
#define PANIC_LED LED_BUILTIN
#define ERROR_DUR 1000

#define SAMPLE_RATE BSEC_SAMPLE_RATE_ULP

/* Forward declarations */
void errLeds(void);
void checkBsecStatus(Bsec2 bsec);
void newDataCallback(const bme68xData data, const bsecOutputs outputs, Bsec2 bsec);

/* Global instances mirroring the Bosch example */
Bsec2 envSensor[NUM_OF_SENS];
comm_mux communicationSetup[NUM_OF_SENS];
uint8_t bsecMemBlock[NUM_OF_SENS][BSEC_INSTANCE_SIZE];
uint8_t sensor = 0;

void setup(void)
{
  /* Desired subscription list of BSEC2 outputs */
  bsecSensor sensorList[] = {
    BSEC_OUTPUT_IAQ,
    BSEC_OUTPUT_RAW_TEMPERATURE,
    BSEC_OUTPUT_RAW_PRESSURE,
    BSEC_OUTPUT_RAW_HUMIDITY,
    BSEC_OUTPUT_RAW_GAS,
    BSEC_OUTPUT_STABILIZATION_STATUS,
    BSEC_OUTPUT_RUN_IN_STATUS,
    BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_TEMPERATURE,
    BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_HUMIDITY,
    BSEC_OUTPUT_STATIC_IAQ,
    BSEC_OUTPUT_CO2_EQUIVALENT,
    BSEC_OUTPUT_BREATH_VOC_EQUIVALENT,
    BSEC_OUTPUT_GAS_PERCENTAGE,
    BSEC_OUTPUT_COMPENSATED_GAS
  };

  Serial.begin(115200);
  comm_mux_begin(Wire, SPI);
  pinMode(PANIC_LED, OUTPUT);
  delay(100);

  while (!Serial) {
    delay(10);
  }

  for (uint8_t i = 0; i < NUM_OF_SENS; i++) {
    communicationSetup[i] = comm_mux_set_config(Wire, SPI, i, communicationSetup[i]);

    envSensor[i].allocateMemory(bsecMemBlock[i]);

    if (!envSensor[i].begin(BME68X_SPI_INTF, comm_mux_read, comm_mux_write, comm_mux_delay, &communicationSetup[i])) {
      checkBsecStatus(envSensor[i]);
    }

    if (SAMPLE_RATE == BSEC_SAMPLE_RATE_ULP) {
      envSensor[i].setTemperatureOffset(TEMP_OFFSET_ULP);
    } else if (SAMPLE_RATE == BSEC_SAMPLE_RATE_LP) {
      envSensor[i].setTemperatureOffset(TEMP_OFFSET_LP);
    }

    if (!envSensor[i].updateSubscription(sensorList, ARRAY_LEN(sensorList), SAMPLE_RATE)) {
      checkBsecStatus(envSensor[i]);
    }

    envSensor[i].attachCallback(newDataCallback);
  }

  Serial.println(
    "BSEC library version " +
    String(envSensor[0].version.major) + "." +
    String(envSensor[0].version.minor) + "." +
    String(envSensor[0].version.major_bugfix) + "." +
    String(envSensor[0].version.minor_bugfix)
  );
}

void loop(void)
{
  for (sensor = 0; sensor < NUM_OF_SENS; sensor++) {
    if (!envSensor[sensor].run()) {
      checkBsecStatus(envSensor[sensor]);
    }
  }
}

void errLeds(void)
{
  while (true) {
    digitalWrite(PANIC_LED, HIGH);
    delay(ERROR_DUR);
    digitalWrite(PANIC_LED, LOW);
    delay(ERROR_DUR);
  }
}

void newDataCallback(const bme68xData data, const bsecOutputs outputs, Bsec2 bsec)
{
  (void)data; /* Data is unused, keep signature to match callback */

  if (!outputs.nOutputs) {
    return;
  }

  Serial.println("BSEC outputs:\n\tSensor num = " + String(sensor));
  Serial.println("\tTime stamp = " + String((int)(outputs.output[0].time_stamp / INT64_C(1000000))));

  for (uint8_t i = 0; i < outputs.nOutputs; i++) {
    const bsecData output = outputs.output[i];

    switch (output.sensor_id) {
      case BSEC_OUTPUT_IAQ:
        Serial.println("\tIAQ = " + String(output.signal));
        Serial.println("\tIAQ accuracy = " + String((int)output.accuracy));
        break;
      case BSEC_OUTPUT_RAW_TEMPERATURE:
        Serial.println("\tTemperature = " + String(output.signal));
        break;
      case BSEC_OUTPUT_RAW_PRESSURE:
        Serial.println("\tPressure = " + String(output.signal));
        break;
      case BSEC_OUTPUT_RAW_HUMIDITY:
        Serial.println("\tHumidity = " + String(output.signal));
        break;
      case BSEC_OUTPUT_RAW_GAS:
        Serial.println("\tGas resistance = " + String(output.signal));
        break;
      case BSEC_OUTPUT_STABILIZATION_STATUS:
        Serial.println("\tStabilization status = " + String(output.signal));
        break;
      case BSEC_OUTPUT_RUN_IN_STATUS:
        Serial.println("\tRun in status = " + String(output.signal));
        break;
      case BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_TEMPERATURE:
        Serial.println("\tCompensated temperature = " + String(output.signal));
        break;
      case BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_HUMIDITY:
        Serial.println("\tCompensated humidity = " + String(output.signal));
        break;
      case BSEC_OUTPUT_STATIC_IAQ:
        Serial.println("\tStatic IAQ = " + String(output.signal));
        break;
      case BSEC_OUTPUT_CO2_EQUIVALENT:
        Serial.println("\tCO2 Equivalent = " + String(output.signal));
        break;
      case BSEC_OUTPUT_BREATH_VOC_EQUIVALENT:
        Serial.println("\tbVOC equivalent = " + String(output.signal));
        break;
      case BSEC_OUTPUT_GAS_PERCENTAGE:
        Serial.println("\tGas percentage = " + String(output.signal));
        break;
      case BSEC_OUTPUT_COMPENSATED_GAS:
        Serial.println("\tCompensated gas = " + String(output.signal));
        break;
      default:
        break;
    }
  }
}

void checkBsecStatus(Bsec2 bsec)
{
  if (bsec.status < BSEC_OK) {
    Serial.println("BSEC error code : " + String(bsec.status));
    errLeds();
  } else if (bsec.status > BSEC_OK) {
    Serial.println("BSEC warning code : " + String(bsec.status));
  }

  if (bsec.sensor.status < BME68X_OK) {
    Serial.println("BME68X error code : " + String(bsec.sensor.status));
    errLeds();
  } else if (bsec.sensor.status > BME68X_OK) {
    Serial.println("BME68X warning code : " + String(bsec.sensor.status));
  }
}

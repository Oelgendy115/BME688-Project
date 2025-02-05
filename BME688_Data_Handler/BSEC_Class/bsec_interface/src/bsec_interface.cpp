#include "bsec_interface.h"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <stdexcept>
#include <vector>

namespace py = pybind11;

//
// C++ Wrapper class for BSEC 2 processing
//
class BSECWrapper {
public:
    BSECWrapper() {
        // Initialize the BSEC library
        if (bsec_init() != BSEC_OK) {
            throw std::runtime_error("BSEC initialization failed.");
        }
    }

    // Process sensor data (here using sensor1 values)
    // Expects temperature, humidity, pressure, gas resistance, and a timestamp (e.g., in milliseconds)
    std::vector<float> process_sensor_data(float temperature, float humidity, float pressure, float gas_resistance, int64_t timestamp) {
        bsec_input_t inputs[4];
        bsec_output_t outputs[10];  // allocate enough space for outputs
        uint8_t num_outputs = 0;

        // Fill in the input data (for sensor 1)
        inputs[0].sensor_id = BSEC_INPUT_TEMPERATURE;
        inputs[0].signal = temperature;
        inputs[0].time_stamp = timestamp;

        inputs[1].sensor_id = BSEC_INPUT_HUMIDITY;
        inputs[1].signal = humidity;
        inputs[1].time_stamp = timestamp;

        inputs[2].sensor_id = BSEC_INPUT_PRESSURE;
        inputs[2].signal = pressure;
        inputs[2].time_stamp = timestamp;

        inputs[3].sensor_id = BSEC_INPUT_GASRESISTOR;
        inputs[3].signal = gas_resistance;
        inputs[3].time_stamp = timestamp;

        // Call BSEC processing function
        if (bsec_do_steps(inputs, 4, outputs, &num_outputs) != BSEC_OK) {
            throw std::runtime_error("BSEC processing failed.");
        }

        // Extract the outputs
        float iaq = -1, static_iaq = -1, co2_eq = -1, voc_eq = -1, accuracy = -1;
        for (int i = 0; i < num_outputs; i++) {
            switch (outputs[i].sensor_id) {
                case BSEC_OUTPUT_IAQ:
                    iaq = outputs[i].signal;
                    break;
                case BSEC_OUTPUT_STATIC_IAQ:
                    static_iaq = outputs[i].signal;
                    break;
                case BSEC_OUTPUT_CO2_EQUIVALENT:
                    co2_eq = outputs[i].signal;
                    break;
                case BSEC_OUTPUT_BREATH_VOC_EQUIVALENT:
                    voc_eq = outputs[i].signal;
                    break;
                case BSEC_OUTPUT_IAQ_ACCURACY:
                    accuracy = outputs[i].signal;
                    break;
                default:
                    break;
            }
        }
        return { iaq, static_iaq, co2_eq, voc_eq, accuracy };
    }
};

//
// pybind11 Module Definition
//
PYBIND11_MODULE(bsec_interface, m) {
    py::class_<BSECWrapper>(m, "BSECWrapper")
        .def(py::init<>())
        .def("process_sensor_data", &BSECWrapper::process_sensor_data,
             "Process sensor data and return [IAQ, Static IAQ, CO2 Equivalent, Breath VOC Equivalent, Accuracy].");
}

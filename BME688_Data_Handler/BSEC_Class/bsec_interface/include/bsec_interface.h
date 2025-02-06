#ifndef BSEC_INTERFACE_H
#define BSEC_INTERFACE_H

#include <stdint.h>
#include <vector>

#ifdef __cplusplus
extern "C" {
#endif

// --- BSEC API Stub Definitions ---
// (In your actual project, include the real BSEC header files provided by Bosch)

#define BSEC_INPUT_TEMPERATURE             0
#define BSEC_INPUT_HUMIDITY                1
#define BSEC_INPUT_PRESSURE                2
#define BSEC_INPUT_GASRESISTOR             3

#define BSEC_OUTPUT_IAQ                    0
#define BSEC_OUTPUT_STATIC_IAQ             1
#define BSEC_OUTPUT_CO2_EQUIVALENT         2
#define BSEC_OUTPUT_BREATH_VOC_EQUIVALENT  3
#define BSEC_OUTPUT_IAQ_ACCURACY           4

#define BSEC_OK                            0

typedef struct {
    uint8_t sensor_id;
    float signal;
    int64_t time_stamp;
} bsec_input_t;

typedef struct {
    uint8_t sensor_id;
    float signal;
} bsec_output_t;

// Stub functions – in your build, these should link to the actual BSEC2 library.
int bsec_init();
int bsec_do_steps(const bsec_input_t *inputs, uint8_t num_inputs, bsec_output_t *outputs, uint8_t *num_outputs);

#ifdef __cplusplus
}
#endif

#endif // BSEC_INTERFACE_H

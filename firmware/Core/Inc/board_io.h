#ifndef BOARD_IO_H
#define BOARD_IO_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

/* Prepare the ADC/DAC converters (PA4 = DAC_OUT1, PA5 = ADC_IN5).
 * Returns true on success. */
bool board_converters_prepare(void);

/* Enable ADC1 and wait for ADRDY. Requires board_converters_prepare(). */
bool board_adc_enable(void);

/* Initialise GPIO, LCD, buttons and LEDs. Called once at boot. */
void board_io_init(void);

/* Poll the debounced buttons. Returns a bitmask of newly-pressed buttons
 * (bit 0 = SW0, ... bit 3 = SW3). */
uint8_t board_buttons_poll(uint32_t now_ms);

/* Write two lines to the 16x2 LCD. Only changed lines are rewritten.
 * NULL lines are displayed blank. */
void board_lcd_show(const char *line1, const char *line2);

/* Drive the status LED: green on healthy, red on fault. */
void board_status(bool fault);

#ifdef __cplusplus
}
#endif

#endif /* BOARD_IO_H */
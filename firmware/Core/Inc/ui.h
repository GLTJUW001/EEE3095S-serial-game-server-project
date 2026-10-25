#ifndef UI_H
#define UI_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* Initialise LEDs and show the initial LCD status. */
void ui_init(void);

/* Non-blocking UI work: SW0 reset, game LED, periodic LCD refresh.
 * Call from the main loop with the current HAL tick. */
void ui_poll(uint32_t now_ms);

#ifdef __cplusplus
}
#endif

#endif /* UI_H */
#ifndef UART_H
#define UART_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

/* Initialise USART1 (PA9 TX / PA10 RX), 115200 8N1, RX interrupt. */
void uart_init(void);

/* USART1 IRQ handler body; call from USART1_IRQHandler(). */
void uart_irq_handler(void);

/* Pop one received byte from the RX ring buffer. Returns false if empty. */
bool uart_rx_pop(uint8_t *byte);

/* Send a NUL-terminated string followed by '\n'. Non-blocking except for a
 * bounded per-byte TX wait. */
void uart_send_line(const char *s);

#ifdef __cplusplus
}
#endif

#endif /* UART_H */
#ifndef PARSER_H
#define PARSER_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

/* Maximum frame length accepted (excluding CR/LF and checksum). */
#define PARSER_FRAME_MAX     32u
/* Drop a stalled partial frame after this many milliseconds. */
#define PARSER_TIMEOUT_MS    500u

/* Clear the frame buffer and timers. */
void parser_init(void);

/* Feed one received byte with the current millisecond timestamp. */
void parser_feed(uint8_t c, uint32_t now_ms);

/* Discard a stalled partial frame and emit NACK:TIMEOUT. Call periodically
 * from the main loop. */
void parser_poll_timeout(uint32_t now_ms);

#ifdef __cplusplus
}
#endif

#endif /* PARSER_H */
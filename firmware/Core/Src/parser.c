#include "parser.h"
#include "server.h"
#include "uart.h"
#include <string.h>

static char     frame[PARSER_FRAME_MAX + 1u];
static uint8_t  len;
static bool     discarding;     /* overflow already reported: skip to next '\n' */
static uint32_t last_byte_ms;

void parser_init(void)
{
    len = 0u;
    discarding = false;
    last_byte_ms = 0u;
}

static int hex_value(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

/* Called once per complete line. Nothing here touches game state; only
 * server_handle() can, and only for a clean, known command. */
static void process_frame(void)
{
    if (len == 0u) { uart_send_line("NACK:BADCMD"); return; }

    /* Garbage: any byte outside printable ASCII (includes the 0xFF marker
     * the UART ISR inserts after a hardware error). */
    for (uint8_t i = 0u; i < len; ++i)
    {
        uint8_t c = (uint8_t)frame[i];
        if (c < 0x20u || c > 0x7Eu) { uart_send_line("NACK:BADCMD"); return; }
    }
    frame[len] = '\0';

    /* Optional checksum suffix "*HH": XOR of every byte before '*'. */
    char *star = strchr(frame, '*');
    if (star != NULL)
    {
        int hi = hex_value(star[1]);
        int lo = (hi >= 0) ? hex_value(star[2]) : -1;
        if (hi < 0 || lo < 0 || star[3] != '\0')
        {
            uart_send_line("NACK:CHECKSUM");
            return;
        }
        uint8_t x = 0u;
        for (const char *p = frame; p < star; ++p) x ^= (uint8_t)*p;
        if (x != (uint8_t)((hi << 4) | lo))
        {
            uart_send_line("NACK:CHECKSUM");
            return;
        }
        *star = '\0';
    }

    server_handle(frame);
}

void parser_feed(uint8_t c, uint32_t now_ms)
{
    last_byte_ms = now_ms;

    if (c == '\r') return;

    if (c == '\n')
    {
        if (discarding) { discarding = false; len = 0u; return; }   /* resynchronised */
        process_frame();
        len = 0u;
        return;
    }

    if (discarding) return;

    if (len >= PARSER_FRAME_MAX)
    {
        discarding = true;
        len = 0u;
        uart_send_line("NACK:OVERFLOW");     /* once per oversized frame */
        return;
    }
    frame[len++] = (char)c;
}

void parser_poll_timeout(uint32_t now_ms)
{
    if ((uint32_t)(now_ms - last_byte_ms) <= PARSER_TIMEOUT_MS) return;

    if (discarding)
    {
        discarding = false;                  /* garbage stream stopped: resync silently */
        len = 0u;
    }
    else if (len > 0u)
    {
        len = 0u;                            /* incomplete frame: drop it */
        uart_send_line("NACK:TIMEOUT");
    }
}

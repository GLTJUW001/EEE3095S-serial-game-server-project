/* Host simulator: runs the REAL firmware parser.c + server.c + game.c on the PC.
 *
 * stdin  = bytes the PC would send over the UART
 * stdout = lines the firmware would transmit (uart_send_line)
 * SIGUSR1 = simulates the SW0 button press (server_button_reset)
 *
 * Only the UART is replaced. Used by tests/firmware_host.py so the pytest
 * suite can be run against the firmware logic without the board.
 */
#define _POSIX_C_SOURCE 200809L
#include "parser.h"
#include "server.h"
#include "uart.h"
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

void uart_send_line(const char *s)
{
    fputs(s, stdout);
    fputc('\n', stdout);
    fflush(stdout);
}

static volatile sig_atomic_t button;
static void on_usr1(int sig) { (void)sig; button = 1; }

static uint32_t millis(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)(ts.tv_sec * 1000u + ts.tv_nsec / 1000000u);
}

int main(void)
{
    struct sigaction sa = {0};
    sa.sa_handler = on_usr1;
    sigaction(SIGUSR1, &sa, NULL);

    server_init();
    parser_init();
    parser_feed(0, millis());   /* prime last_byte_ms like a boot-time tick */
    parser_init();

    for (;;)
    {
        struct pollfd p = { .fd = STDIN_FILENO, .events = POLLIN };
        int r = poll(&p, 1, 5);           /* main-loop tick ~5 ms */
        uint32_t now = millis();

        if (button) { button = 0; server_button_reset(); }

        if (r > 0 && (p.revents & (POLLIN | POLLHUP)))
        {
            unsigned char buf[256];
            ssize_t n = read(STDIN_FILENO, buf, sizeof buf);
            if (n <= 0) return 0;
            for (ssize_t i = 0; i < n; ++i) parser_feed(buf[i], now);
        }
        parser_poll_timeout(now);
    }
}

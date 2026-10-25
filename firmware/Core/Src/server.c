#include "server.h"
#include "game.h"
#include "uart.h"
#include <stdarg.h>
#include <string.h>

static srv_state_t state = SRV_IDLE;

/* Every reply goes through here: concatenate NULL-terminated parts, send. */
static void send_cat(const char *first, ...)
{
    char out[40];
    uint8_t n = 0;
    va_list ap;
    va_start(ap, first);
    for (const char *p = first; p != NULL; p = va_arg(ap, const char *))
    {
        while (*p != '\0' && n < sizeof out - 1u) out[n++] = *p++;
    }
    va_end(ap);
    out[n] = '\0';
    uart_send_line(out);
}

static void nack(const char *reason) { send_cat("NACK:", reason, (const char *)NULL); }

void server_init(void)
{
    game_reset();
    state = SRV_IDLE;
}

srv_state_t server_state(void) { return state; }

void server_button_reset(void)
{
    game_reset();
    state = SRV_IDLE;
    uart_send_line("EVT:RESET");
}

/* Parse an optionally negative decimal index. Large values are clamped so
 * they reach the range check instead of overflowing. */
static bool parse_index(const char *s, int *out)
{
    bool neg = false;
    int value = 0;
    int digits = 0;
    if (*s == '-') { neg = true; ++s; }
    while (*s >= '0' && *s <= '9')
    {
        if (value < 1000) value = value * 10 + (*s - '0');
        ++digits;
        ++s;
    }
    if (digits == 0 || *s != '\0') return false;
    *out = neg ? -value : value;
    return true;
}

static void handle_move(const char *args)
{
    char mark = 0;
    int idx = 0;
    char winner[2] = {0, 0};

    /* 1. Syntax: "<i>" or "<X|O>:<i>". No state is touched here. */
    if (args[0] != '\0' && args[1] == ':')
    {
        if (args[0] != 'X' && args[0] != 'O') { nack("BADCMD"); return; }
        mark = args[0];
        args += 2;
    }
    if (!parse_index(args, &idx)) { nack("BADCMD"); return; }

    /* 2. Server state. */
    if (state != SRV_PLAY) { nack("NOGAME"); return; }

    /* 3. Rules (turn, range, occupied) live in game_move; it writes the
     *    board only after all of them pass. */
    switch (game_move(mark, idx))
    {
    case G_NOTURN:   nack("NOTURN");   return;
    case G_RANGE:    nack("RANGE");    return;
    case G_OCCUPIED: nack("OCCUPIED"); return;
    case G_OVER:     nack("NOGAME");   return;
    case G_OK:       break;
    }

    switch (game_status())
    {
    case GS_WIN:
        state = SRV_OVER;
        winner[0] = game_winner();
        send_cat("WIN:", winner, ":", game_board(), (const char *)NULL);
        break;
    case GS_DRAW:
        state = SRV_OVER;
        send_cat("DRAW:", game_board(), (const char *)NULL);
        break;
    default:
        send_cat("OK:BOARD:", game_board(), (const char *)NULL);
        break;
    }
}

void server_handle(const char *cmd)
{
    if (strcmp(cmd, "CONNECT") == 0)
    {
        if (state == SRV_IDLE) uart_send_line("OK"); else nack("BUSY");
    }
    else if (strcmp(cmd, "NEW") == 0)
    {
        if (state == SRV_PLAY) { nack("BUSY"); return; }
        game_reset();
        state = SRV_PLAY;
        send_cat("OK:BOARD:", game_board(), (const char *)NULL);
    }
    else if (strncmp(cmd, "MOVE:", 5) == 0)
    {
        handle_move(cmd + 5);
    }
    else if (strcmp(cmd, "STATE") == 0)
    {
        char turn[2] = {'-', 0};
        if (state == SRV_IDLE) { nack("NOGAME"); return; }
        if (state == SRV_PLAY) turn[0] = game_turn();
        send_cat("BOARD:", game_board(), ":", turn, ":",
                 (state == SRV_PLAY) ? "PLAY" : "OVER", (const char *)NULL);
    }
    else if (strcmp(cmd, "RESIGN") == 0)
    {
        if (state != SRV_PLAY) { nack("NOGAME"); return; }
        state = SRV_OVER;
        uart_send_line("OK:GAMEOVER");
    }
    else if (strcmp(cmd, "DISCONNECT") == 0)
    {
        game_reset();
        state = SRV_IDLE;
        uart_send_line("OK");
    }
    else
    {
        nack("BADCMD");
    }
}

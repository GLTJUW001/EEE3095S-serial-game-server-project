#include "ui.h"
#include "board_io.h"
#include "game.h"
#include "server.h"
#include "main.h"

#define LED_GREEN_PIN   11u              /* PB11 */
#define LED_RED_PIN     10u              /* PB10 */
#define BLINK_HALF_MS   250u             /* 2 Hz */
#define LCD_PERIOD_MS   100u             /* board_lcd_show only writes changed lines */

static uint32_t last_lcd_ms;

static void led_green(bool on)
{
    GPIOB->BSRR = on ? (1u << LED_GREEN_PIN) : (1u << (LED_GREEN_PIN + 16u));
}

/* Copy src (including its NUL) to dst. */
static void put(char *dst, const char *src)
{
    while ((*dst++ = *src++) != '\0') {}
}

static void lcd_refresh(void)
{
    char l1[17];
    char l2[17];
    const char *b = game_board();
    srv_state_t st = server_state();

    if (st == SRV_IDLE)
    {
        board_lcd_show("IDLE", "Waiting for PC");
        return;
    }

    if (st == SRV_PLAY)
    {
        l1[0] = game_turn();
        put(&l1[1], " to move");
    }
    else if (game_status() == GS_WIN)
    {
        l1[0] = game_winner();
        put(&l1[1], " wins!");
    }
    else if (game_status() == GS_DRAW)
    {
        put(l1, "Draw");
    }
    else
    {
        put(l1, "Resigned");
    }

    /* Board as three rows: XOX|.O.|..X */
    uint8_t k = 0;
    for (uint8_t r = 0; r < 3u; ++r)
    {
        for (uint8_t c = 0; c < 3u; ++c) l2[k++] = b[r * 3u + c];
        if (r < 2u) l2[k++] = '|';
    }
    l2[k] = '\0';

    board_lcd_show(l1, l2);
}

void ui_init(void)
{
    GPIOB->BSRR = (1u << (LED_RED_PIN + 16u));   /* red off */
    led_green(false);                            /* board_io_init left green on */
    last_lcd_ms = 0u;
    lcd_refresh();
}

void ui_poll(uint32_t now_ms)
{
    /* Button: board_buttons_poll() already debounces (20 ms). Bit 0 = SW0. */
    if ((board_buttons_poll(now_ms) & 0x01u) != 0u)
    {
        server_button_reset();
    }

    switch (server_state())
    {
    case SRV_PLAY: led_green(game_turn() == 'X'); break;
    case SRV_OVER: led_green(((now_ms / BLINK_HALF_MS) & 1u) != 0u); break;
    default:       led_green(false); break;
    }

    if ((uint32_t)(now_ms - last_lcd_ms) >= LCD_PERIOD_MS)
    {
        last_lcd_ms = now_ms;
        lcd_refresh();
    }
}

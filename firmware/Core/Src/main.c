/* EEE3095S CS Project 2026: Serial Game Server (Tic-Tac-Toe).
 * STM32F051 is the authoritative game server; the PC GUI is a thin client.
 *
 * Supplied infrastructure kept from the earlier practical: clock setup,
 * board_io (LCD, debounced buttons, LEDs). New modules:
 *   uart    - USART1 (PA9 TX / PA10 RX), interrupt-driven RX ring buffer
 *   parser  - frame assembly, length/timeout/garbage handling, dispatch
 *   server  - IDLE / IN_PROGRESS / GAME_OVER state machine
 *   game    - pure board logic (validation, turn, win/draw)
 *   ui      - SW0 reset button, game LED, optional LCD status
 *
 * Rule for this file: nothing in the main loop may block.
 * No HAL_Delay(), no unbounded waits.
 */
#include "main.h"
#include "board_io.h"
#include "uart.h"
#include "parser.h"
#include "server.h"
#include "ui.h"

/* Maximum bytes moved from the RX ring buffer per loop pass, so that the
 * button, LED and LCD work still runs even under a continuous byte stream. */
#define RX_BYTES_PER_PASS 64u

int main(void)
{
    HAL_Init();
    SystemClock_Config();       /* 8 MHz HSE -> PLL x6 -> 48 MHz */
    board_io_init();            /* GPIO, LCD, buttons, LEDs (uses HAL_Delay once, at boot) */
    board_lcd_show("Serial Game Srv", "Starting...");

    uart_init();                /* USART1 115200 8N1, RX interrupt enabled */
    server_init();              /* state = IDLE, empty game */
    parser_init();              /* clear frame buffer and timers */
    ui_init();                  /* LED off, LCD shows IDLE */

    while (1)
    {
        uint32_t now = HAL_GetTick();

        /* 1. Drain received bytes into the frame parser. */
        uint8_t byte;
        for (uint32_t n = 0u; n < RX_BYTES_PER_PASS && uart_rx_pop(&byte); ++n)
        {
            parser_feed(byte, now);
        }

        /* 2. Discard a stalled partial frame after 500 ms (NACK:TIMEOUT). */
        parser_poll_timeout(now);

        /* 3. SW0 button, game LED and LCD. Non-blocking apart from the
         *    short LCD write that only happens when the text changes. */
        ui_poll(now);
    }
}

/* Supplied: 8 MHz crystal -> PLL x6 -> 48 MHz, undivided AHB/APB.
 * HAL_RCC_ClockConfig also updates the SysTick millisecond time base. */
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef oscillator = {0};
    RCC_ClkInitTypeDef clocks = {0};
    oscillator.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    oscillator.HSEState = RCC_HSE_ON;
    oscillator.PLL.PLLState = RCC_PLL_ON;
    oscillator.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    oscillator.PLL.PREDIV = RCC_PREDIV_DIV1;
    oscillator.PLL.PLLMUL = RCC_PLL_MUL6;
    if (HAL_RCC_OscConfig(&oscillator) != HAL_OK) Error_Handler();

    clocks.ClockType = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK
                     | RCC_CLOCKTYPE_PCLK1;
    clocks.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clocks.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clocks.APB1CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&clocks, FLASH_LATENCY_1) != HAL_OK) Error_Handler();
}

/* Reached only if clock setup fails at boot. Runtime faults are handled by
 * HardFault_Handler (software reset) in stm32f0xx_it.c instead. */
void Error_Handler(void)
{
    __disable_irq();
    while (1) {}
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{
    (void)file;
    (void)line;
    Error_Handler();
}
#endif

#include "uart.h"
#include "main.h"

#define RX_BUF_SZ   128u               /* power of two */
#define TX_POLLS    100000u            /* bounded wait per byte, never forever */
#define BAUD        115200u
#define PCLK_HZ     48000000u
#define BAD_BYTE    0xFFu              /* marker inserted when the hardware reports an error */

static volatile uint8_t rx_buf[RX_BUF_SZ];
static volatile uint8_t rx_head;       /* written by ISR only  */
static volatile uint8_t rx_tail;       /* written by main only */
static volatile uint32_t rx_dropped;   /* development evidence: bytes lost to a full buffer */

static void rx_push(uint8_t b)
{
    uint8_t next = (uint8_t)((rx_head + 1u) & (RX_BUF_SZ - 1u));
    if (next == rx_tail) { ++rx_dropped; return; }   /* full: drop, never block */
    rx_buf[rx_head] = b;
    rx_head = next;
}

void uart_init(void)
{
    RCC->AHBENR  |= RCC_AHBENR_GPIOAEN;
    RCC->APB2ENR |= RCC_APB2ENR_USART1EN;
    (void)RCC->APB2ENR;

    /* PA9 = TX, PA10 = RX: alternate function 1, pull-up on RX so a
     * disconnected adapter reads as idle rather than noise. */
    GPIOA->MODER  = (GPIOA->MODER  & ~((3u << 18) | (3u << 20))) | (2u << 18) | (2u << 20);
    GPIOA->AFR[1] = (GPIOA->AFR[1] & ~((0xFu << 4) | (0xFu << 8))) | (1u << 4) | (1u << 8);
    GPIOA->PUPDR  = (GPIOA->PUPDR  & ~(3u << 20)) | (1u << 20);

    USART1->CR1 = 0u;
    USART1->BRR = (PCLK_HZ + BAUD / 2u) / BAUD;      /* 417 -> 0.08 % error */
    USART1->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NCF;
    rx_head = rx_tail = 0u;
    USART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_RXNEIE | USART_CR1_UE;

    NVIC_SetPriority(USART1_IRQn, 2u);
    NVIC_EnableIRQ(USART1_IRQn);
}

void uart_irq_handler(void)
{
    uint32_t isr = USART1->ISR;

    if (isr & (USART_ISR_ORE | USART_ISR_FE | USART_ISR_NE))
    {
        /* Clear the flags (an uncleared ORE stalls reception) and insert a
         * non-printable marker so the parser rejects the damaged frame
         * instead of silently seeing a shorter, still-valid command. */
        USART1->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NCF;
        if (isr & USART_ISR_RXNE) (void)USART1->RDR;
        rx_push(BAD_BYTE);
        return;
    }
    if (isr & USART_ISR_RXNE)
    {
        rx_push((uint8_t)USART1->RDR);   /* reading RDR clears RXNE */
    }
}

bool uart_rx_pop(uint8_t *byte)
{
    if (rx_tail == rx_head) return false;
    *byte = rx_buf[rx_tail];
    rx_tail = (uint8_t)((rx_tail + 1u) & (RX_BUF_SZ - 1u));
    return true;
}

static bool tx_byte(uint8_t b)
{
    for (uint32_t t = TX_POLLS; t != 0u; --t)
    {
        if (USART1->ISR & USART_ISR_TXE)
        {
            USART1->TDR = b;
            return true;
        }
    }
    return false;
}

void uart_send_line(const char *s)
{
    while (*s != '\0')
    {
        if (!tx_byte((uint8_t)*s++)) return;
    }
    (void)tx_byte((uint8_t)'\n');
}

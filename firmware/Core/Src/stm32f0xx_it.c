/* Core exception handlers, the HAL millisecond time base and USART1. */
#include "main.h"
#include "stm32f0xx_it.h"
#include "uart.h"

void NMI_Handler(void)
{
    Error_Handler();
}

/* Recover instead of hanging: a software reset returns the server to IDLE. */
void HardFault_Handler(void)
{
    NVIC_SystemReset();
}

void SVC_Handler(void)
{
}

void PendSV_Handler(void)
{
}

void SysTick_Handler(void)
{
    HAL_IncTick();
}

void USART1_IRQHandler(void)
{
    uart_irq_handler();
}

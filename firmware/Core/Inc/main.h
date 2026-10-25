#ifndef MAIN_H
#define MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f0xx_hal.h"

/* 8 MHz HSE -> PLL x6 -> 48 MHz. */
void SystemClock_Config(void);

/* Fatal boot error: disable interrupts and hang. */
void Error_Handler(void);

#ifdef __cplusplus
}
#endif

#endif /* MAIN_H */
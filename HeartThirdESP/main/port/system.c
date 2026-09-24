/************************************************************************************
* @file     : system.c
* @brief    : ESP timer based clock and startup delay.
* @details  : Delays in the converter driver occur only during initialization.
***********************************************************************************/
#include "system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

/** @brief Return elapsed milliseconds since boot. */
uint32_t systemGetTickMs(void) {
    return (uint32_t)(esp_timer_get_time() / 1000LL);
}

/** @brief Sleep during converter initialization. */
int8_t systemDelayMs(uint32_t delayMs) {
    vTaskDelay(pdMS_TO_TICKS(delayMs) + 1U);
    return SYSTEM_OK;
}
/**************************End of file********************************/

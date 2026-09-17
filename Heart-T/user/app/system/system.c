/************************************************************************************
* @file     : system.c
* @brief    : HeartThird system state and firmware information.
* @details  : Uses the TIM2-backed HAL millisecond clock.
* @author   :
* @date     :
* @version  :
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "system.h"
#include "stm32f1xx_hal.h"

static eSystemMode gSystemMode = E_SYSTEM_INIT_MODE;

/** @brief Reset the system state during bare-metal startup. */
void systemInit(void) {
    gSystemMode = E_SYSTEM_INIT_MODE;
}

/** @brief Validate both lower and upper bounds of a mode. */
bool systemIsValidMode(eSystemMode mode) {
    return (mode >= E_SYSTEM_INIT_MODE) && (mode < E_SYSTEM_MODE_MAX);
}

/** @brief Read the shared mode from main-loop context. */
eSystemMode systemGetMode(void) {
    return gSystemMode;
}

/** @brief Update the shared mode from main-loop context. */
int8_t systemSetMode(eSystemMode mode) {
    if (!systemIsValidMode(mode)) {
        return SYSTEM_ERROR_PARAM;
    }

    gSystemMode = mode;
    return SYSTEM_OK;
}

/** @brief Return the readable name of a mode. */
const char *systemGetModeString(eSystemMode mode) {
    switch (mode) {
        case E_SYSTEM_INIT_MODE: return "INIT";
        case E_SYSTEM_STANDBY_MODE: return "STANDBY";
        case E_SYSTEM_NORMAL_MODE: return "NORMAL";
        case E_SYSTEM_FAULT_MODE: return "FAULT";
        default: return "UNKNOWN";
    }
}

/** @brief Read the TIM2 uptime in milliseconds. */
uint32_t systemGetTickMs(void) {
    return HAL_GetTick();
}

/** @brief Wait during startup only; periodic services must not call this delay. */
int8_t systemDelayMs(uint32_t delayMs) {
    HAL_Delay(delayMs);
    return SYSTEM_OK;
}

/** @brief Return the HeartThird firmware name. */
const char *systemGetFirmwareName(void) {
    return FIRMWARE_NAME;
}

/** @brief Return the configured firmware version. */
const char *systemGetFirmwareVersion(void) {
    return FIRMWARE_VERSION;
}

/** @brief Return the configured hardware version. */
const char *systemGetHardwareVersion(void) {
    return HARDWARE_VERSION;
}

/**************************End of file********************************/

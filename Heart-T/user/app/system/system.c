/************************************************************************************
* @file     : system.c
* @brief    : HeartThird system state and firmware information.
* @details  : Uses RTOS timing without reconfiguring the MCU SysTick.
* @author   :
* @date     :
* @version  :
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "system.h"
#include "rtos.h"

static eSystemMode gSystemMode = E_SYSTEM_INIT_MODE;

/** @brief Reset the system state before the scheduler starts. */
void systemInit(void) {
    gSystemMode = E_SYSTEM_INIT_MODE;
}

/** @brief Validate both lower and upper bounds of a mode. */
bool systemIsValidMode(eSystemMode mode) {
    return (mode >= E_SYSTEM_INIT_MODE) && (mode < E_SYSTEM_MODE_MAX);
}

/** @brief Read the shared mode from task context. */
eSystemMode systemGetMode(void) {
    eSystemMode lMode;

    repRtosEnterCritical();
    lMode = gSystemMode;
    repRtosExitCritical();
    return lMode;
}

/** @brief Update the shared mode from task context. */
int8_t systemSetMode(eSystemMode mode) {
    if (!systemIsValidMode(mode)) {
        return REP_RTOS_STATUS_INVALID_PARAM;
    }

    repRtosEnterCritical();
    gSystemMode = mode;
    repRtosExitCritical();
    return REP_RTOS_STATUS_OK;
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

/** @brief Read the RTOS uptime in milliseconds. */
uint32_t systemGetTickMs(void) {
    return repRtosGetTickMs();
}

/** @brief Block the calling task without busy waiting. */
int8_t systemDelayMs(uint32_t delayMs) {
    return repRtosTaskDelayMs(delayMs);
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

/************************************************************************************
* @file     : system.h
* @brief    : HeartThird system state and firmware information.
* @details  : TIM2 provides the 1 ms clock for the bare-metal main loop.
* @author   :
* @date     :
* @version  :
* @copyright: Copyright (c) 2050
***********************************************************************************/
#ifndef HEARTTHIRD_SYSTEM_H
#define HEARTTHIRD_SYSTEM_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SYSTEM_OK                      1
#define SYSTEM_ERROR_PARAM             (-1)

#define SYSTEM_STRINGIFY_IMPL(value)    #value
#define SYSTEM_STRINGIFY(value)         SYSTEM_STRINGIFY_IMPL(value)
#define FIRMWARE_NAME                   "HeartThird"
#define FW_VER_MAJOR                    1
#define FW_VER_MINOR                    0
#define FW_VER_PATCH                    0
#define HW_VER_MAJOR                    1
#define HW_VER_MINOR                    0
#define HW_VER_PATCH                    0
#define FIRMWARE_VERSION                "V" SYSTEM_STRINGIFY(FW_VER_MAJOR) "." SYSTEM_STRINGIFY(FW_VER_MINOR) "." SYSTEM_STRINGIFY(FW_VER_PATCH)
#define HARDWARE_VERSION                "v" SYSTEM_STRINGIFY(HW_VER_MAJOR) "." SYSTEM_STRINGIFY(HW_VER_MINOR) "." SYSTEM_STRINGIFY(HW_VER_PATCH)

typedef enum eSystemMode {
    E_SYSTEM_INIT_MODE = 0,
    E_SYSTEM_STANDBY_MODE,
    E_SYSTEM_NORMAL_MODE,
    E_SYSTEM_FAULT_MODE,
    E_SYSTEM_MODE_MAX,
} eSystemMode;

/* Initialize before services. Mode access is main-loop only. */
void systemInit(void);
bool systemIsValidMode(eSystemMode mode);
eSystemMode systemGetMode(void);
/* Returns SYSTEM_OK or SYSTEM_ERROR_PARAM. */
int8_t systemSetMode(eSystemMode mode);
const char *systemGetModeString(eSystemMode mode);
/* Tick reads support main/ISR context; delay is blocking and startup-only. */
uint32_t systemGetTickMs(void);
int8_t systemDelayMs(uint32_t delayMs);
const char *systemGetFirmwareName(void);
const char *systemGetFirmwareVersion(void);
const char *systemGetHardwareVersion(void);

#ifdef __cplusplus
}
#endif

#endif /* HEARTTHIRD_SYSTEM_H */

/**************************End of file********************************/

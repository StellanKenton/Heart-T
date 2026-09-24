/************************************************************************************
* @file     : system.h
* @brief    : ESP32-S3 system state and time source.
* @details  : Application state has a single acquisition-task owner.
***********************************************************************************/
#ifndef HEARTTHIRD_ESP_SYSTEM_H
#define HEARTTHIRD_ESP_SYSTEM_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define SYSTEM_OK 1
#define FIRMWARE_NAME "HeartThirdESP"
#define FIRMWARE_VERSION "V1.0.0"
#define HARDWARE_VERSION "ESP32-S3"
uint32_t systemGetTickMs(void);
int8_t systemDelayMs(uint32_t delayMs);
#ifdef __cplusplus
}
#endif
#endif
/**************************End of file********************************/

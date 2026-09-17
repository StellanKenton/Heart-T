/************************************************************************************
* @file     : usbd_conf.h
* @brief    : USB Device library configuration and static allocator.
* @details  : STM32F103 full-speed CDC, static storage and bounded cooperative work.
* @author   :
* @date     : 2026-09-17
* @version  : 1.0
* @copyright: Copyright (c) 2050
***********************************************************************************/
#ifndef USER_DRIVER_USBD_CONF_H
#define USER_DRIVER_USBD_CONF_H
#include "stm32f1xx_hal.h"
#include <stddef.h>
#include <string.h>
#ifdef __cplusplus
extern "C" {
#endif
#define USBD_MAX_NUM_INTERFACES 2U
#define USBD_MAX_NUM_CONFIGURATION 1U
#define USBD_MAX_STR_DESC_SIZ 64U
#define USBD_SELF_POWERED 0U
#define USBD_DEBUG_LEVEL 0U
#define USBD_LPM_ENABLED 0U
#define USBD_SUPPORT_USER_STRING_DESC 0U
#define USBD_CLASS_USER_STRING_DESC 0U
#define USBD_CLASS_BOS_ENABLED 0U
#define USBD_malloc drvUsbStaticAlloc
#define USBD_free drvUsbStaticFree
#define USBD_memset memset
#define USBD_memcpy memcpy
#define USBD_Delay HAL_Delay
void *drvUsbStaticAlloc(uint32_t size);
void drvUsbStaticFree(void *memory);
#ifdef __cplusplus
}
#endif
#endif /* USER_DRIVER_USBD_CONF_H */
/**************************End of file********************************/

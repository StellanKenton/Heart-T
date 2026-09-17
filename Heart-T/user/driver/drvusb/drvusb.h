/************************************************************************************
* @file     : drvusb.h
* @brief    : USB CDC echo service.
* @details  : STM32F103 full-speed CDC, static storage and bounded cooperative work.
* @author   :
* @date     : 2026-09-17
* @version  : 1.0
* @copyright: Copyright (c) 2050
***********************************************************************************/
#ifndef USER_DRIVER_DRVUSB_H
#define USER_DRIVER_DRVUSB_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define DRV_USB_OK             1
#define DRV_USB_ERROR_STATE    (-10)
#define DRV_USB_ERROR_TRANSFER (-11)
#define DRV_USB_PACKET_SIZE    64U
/* Main-loop only, once after MX_USB_PCD_Init. */
int8_t drvUsbInit(void);
/* Main-loop only: echo at most one packet; disconnected/busy is normal idle. */
int8_t drvUsbEchoProcess(void);
#ifdef __cplusplus
}
#endif
#endif /* USER_DRIVER_DRVUSB_H */
/**************************End of file********************************/

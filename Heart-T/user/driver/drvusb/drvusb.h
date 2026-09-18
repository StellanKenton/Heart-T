/************************************************************************************
* @file     : drvusb.h
* @brief    : USB CDC buffered two-channel sample streaming.
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
#define DRV_USB_SAMPLE_CAPACITY 40U
#define DRV_USB_SAMPLES_PER_FRAME 5U
#define DRV_USB_FRAME_SIZE     33U
#define DRV_USB_FRAME_HEADER   0xFAU
#define DRV_USB_CRC_POLYNOMIAL 0x07U
#define DRV_USB_DISCONNECT_MS  100U
/* Startup only, before MX_USB_PCD_Init enables the USB peripheral. */
void drvUsbDisconnect(void);
/* Main-loop only, once after MX_USB_PCD_Init. */
int8_t drvUsbInit(void);
/* Main-loop only: copy one simultaneous channel pair into the sample ring. */
void drvUsbQueueSample(const int32_t channel[2]);
/* Main-loop only: submit at most one frame; disconnected/busy retains the ring. */
int8_t drvUsbStreamProcess(void);
/* Main-loop only: number of sample pairs discarded by ring overflow. */
uint32_t drvUsbGetDroppedSamples(void);
#ifdef __cplusplus
}
#endif
#endif /* USER_DRIVER_DRVUSB_H */
/**************************End of file********************************/

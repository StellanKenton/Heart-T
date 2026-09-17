/************************************************************************************
* @file     : usbd_conf.c
* @brief    : USB Device library to STM32 HAL binding.
* @details  : STM32F103 full-speed CDC, static storage and bounded cooperative work.
* @author   :
* @date     : 2026-09-17
* @version  : 1.0
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "usbd_core.h"
#include "usbd_cdc.h"
#include "usb.h"

/** @brief Convert HAL peripheral status to the USB library status. */
static USBD_StatusTypeDef drvUsbHalStatus(HAL_StatusTypeDef status) {
    if (status == HAL_OK) {
        return USBD_OK;
    }
    return (status == HAL_BUSY) ? USBD_BUSY : USBD_FAIL;
}

/** @brief Bind the initialized PCD and allocate nonoverlapping 512-byte PMA regions. */
USBD_StatusTypeDef USBD_LL_Init(USBD_HandleTypeDef *device) {
    hpcd_USB_FS.pData = device;
    device->pData = &hpcd_USB_FS;
    /* BTABLE 0x00..0x3F; EP0 OUT/IN, CDC IN/OUT and notification IN. */
    if ((HAL_PCDEx_PMAConfig(&hpcd_USB_FS, 0x00U, PCD_SNG_BUF, 0x40U) != HAL_OK) ||
        (HAL_PCDEx_PMAConfig(&hpcd_USB_FS, 0x80U, PCD_SNG_BUF, 0x80U) != HAL_OK) ||
        (HAL_PCDEx_PMAConfig(&hpcd_USB_FS, CDC_IN_EP, PCD_SNG_BUF, 0xC0U) != HAL_OK) ||
        (HAL_PCDEx_PMAConfig(&hpcd_USB_FS, CDC_OUT_EP, PCD_SNG_BUF, 0x100U) != HAL_OK) ||
        (HAL_PCDEx_PMAConfig(&hpcd_USB_FS, CDC_CMD_EP, PCD_SNG_BUF, 0x140U) != HAL_OK)) {
        return USBD_FAIL;
    }
    return USBD_OK;
}

/** @brief Forward DeInit to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_DeInit(USBD_HandleTypeDef *device) {
    HAL_NVIC_DisableIRQ(USB_LP_CAN1_RX0_IRQn);
    return drvUsbHalStatus(HAL_PCD_DeInit((PCD_HandleTypeDef *)device->pData));
}

/** @brief Forward Start to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_Start(USBD_HandleTypeDef *device) {
    return drvUsbHalStatus(HAL_PCD_Start((PCD_HandleTypeDef *)device->pData));
}

/** @brief Forward Stop to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_Stop(USBD_HandleTypeDef *device) {
    return drvUsbHalStatus(HAL_PCD_Stop((PCD_HandleTypeDef *)device->pData));
}

/** @brief Forward OpenEP to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_OpenEP(USBD_HandleTypeDef *device, uint8_t address, uint8_t type, uint16_t size) {
    return drvUsbHalStatus(HAL_PCD_EP_Open((PCD_HandleTypeDef *)device->pData, address, size, type));
}

/** @brief Forward CloseEP to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_CloseEP(USBD_HandleTypeDef *device, uint8_t address) {
    return drvUsbHalStatus(HAL_PCD_EP_Close((PCD_HandleTypeDef *)device->pData, address));
}

/** @brief Forward FlushEP to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_FlushEP(USBD_HandleTypeDef *device, uint8_t address) {
    return drvUsbHalStatus(HAL_PCD_EP_Flush((PCD_HandleTypeDef *)device->pData, address));
}

/** @brief Forward StallEP to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_StallEP(USBD_HandleTypeDef *device, uint8_t address) {
    return drvUsbHalStatus(HAL_PCD_EP_SetStall((PCD_HandleTypeDef *)device->pData, address));
}

/** @brief Forward ClearStallEP to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_ClearStallEP(USBD_HandleTypeDef *device, uint8_t address) {
    return drvUsbHalStatus(HAL_PCD_EP_ClrStall((PCD_HandleTypeDef *)device->pData, address));
}

/** @brief Forward SetUSBAddress to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_SetUSBAddress(USBD_HandleTypeDef *device, uint8_t address) {
    return drvUsbHalStatus(HAL_PCD_SetAddress((PCD_HandleTypeDef *)device->pData, address));
}

/** @brief Forward Transmit to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_Transmit(USBD_HandleTypeDef *device, uint8_t address, uint8_t *buffer, uint32_t size) {
    return drvUsbHalStatus(HAL_PCD_EP_Transmit((PCD_HandleTypeDef *)device->pData, address, buffer, size));
}

/** @brief Forward PrepareReceive to the HAL peripheral driver. */
USBD_StatusTypeDef USBD_LL_PrepareReceive(USBD_HandleTypeDef *device, uint8_t address, uint8_t *buffer, uint32_t size) {
    return drvUsbHalStatus(HAL_PCD_EP_Receive((PCD_HandleTypeDef *)device->pData, address, buffer, size));
}

/** @brief Inspect the endpoint stall state. */
uint8_t USBD_LL_IsStallEP(USBD_HandleTypeDef *device, uint8_t address) {
    PCD_HandleTypeDef *lPcd = (PCD_HandleTypeDef *)device->pData;
    return (address & 0x80U) ? lPcd->IN_ep[address & 0x7FU].is_stall : lPcd->OUT_ep[address & 0x7FU].is_stall;
}

/** @brief Read the actual received byte count. */
uint32_t USBD_LL_GetRxDataSize(USBD_HandleTypeDef *device, uint8_t address) {
    return HAL_PCD_EP_GetRxCount((PCD_HandleTypeDef *)device->pData, address);
}

/** @brief Provide the library startup delay hook. */
void USBD_LL_Delay(uint32_t delayMs) {
    HAL_Delay(delayMs);
}

/** @brief Dispatch SetupStage from USB ISR context to the device core. */
void HAL_PCD_SetupStageCallback(PCD_HandleTypeDef *pcd) {
    (void)USBD_LL_SetupStage((USBD_HandleTypeDef *)pcd->pData, (uint8_t *)pcd->Setup);
}

/** @brief Dispatch DataOutStage from USB ISR context to the device core. */
void HAL_PCD_DataOutStageCallback(PCD_HandleTypeDef *pcd, uint8_t endpoint) {
    (void)USBD_LL_DataOutStage((USBD_HandleTypeDef *)pcd->pData, endpoint, pcd->OUT_ep[endpoint].xfer_buff);
}

/** @brief Dispatch DataInStage from USB ISR context to the device core. */
void HAL_PCD_DataInStageCallback(PCD_HandleTypeDef *pcd, uint8_t endpoint) {
    (void)USBD_LL_DataInStage((USBD_HandleTypeDef *)pcd->pData, endpoint, pcd->IN_ep[endpoint].xfer_buff);
}

/** @brief Dispatch SOF from USB ISR context to the device core. */
void HAL_PCD_SOFCallback(PCD_HandleTypeDef *pcd) {
    (void)USBD_LL_SOF((USBD_HandleTypeDef *)pcd->pData);
}

/** @brief Dispatch Suspend from USB ISR context to the device core. */
void HAL_PCD_SuspendCallback(PCD_HandleTypeDef *pcd) {
    (void)USBD_LL_Suspend((USBD_HandleTypeDef *)pcd->pData);
}

/** @brief Dispatch Resume from USB ISR context to the device core. */
void HAL_PCD_ResumeCallback(PCD_HandleTypeDef *pcd) {
    (void)USBD_LL_Resume((USBD_HandleTypeDef *)pcd->pData);
}

/** @brief Dispatch Connect from USB ISR context to the device core. */
void HAL_PCD_ConnectCallback(PCD_HandleTypeDef *pcd) {
    (void)USBD_LL_DevConnected((USBD_HandleTypeDef *)pcd->pData);
}

/** @brief Dispatch Disconnect from USB ISR context to the device core. */
void HAL_PCD_DisconnectCallback(PCD_HandleTypeDef *pcd) {
    (void)USBD_LL_DevDisconnected((USBD_HandleTypeDef *)pcd->pData);
}

/** @brief Reinitialize full-speed control endpoints and clear the old CDC session. */
void HAL_PCD_ResetCallback(PCD_HandleTypeDef *pcd) {
    USBD_HandleTypeDef *lDevice = (USBD_HandleTypeDef *)pcd->pData;
    (void)USBD_LL_SetSpeed(lDevice, USBD_SPEED_FULL);
    (void)USBD_LL_Reset(lDevice);
}
/**************************End of file********************************/

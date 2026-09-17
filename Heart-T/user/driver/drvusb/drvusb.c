/************************************************************************************
* @file     : drvusb.c
* @brief    : CDC descriptors, packet ownership and echo processing.
* @details  : STM32F103 full-speed CDC, static storage and bounded cooperative work.
* @author   :
* @date     : 2026-09-17
* @version  : 1.0
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "drvusb.h"
#include "usb.h"
#include "usbd_core.h"
#include "usbd_cdc.h"
#include <stdbool.h>

static USBD_HandleTypeDef gUsbDevice;
static USBD_CDC_HandleTypeDef gCdcStorage;
static bool gAllocated = false;
static bool gReady = false;
static uint8_t gPacket[DRV_USB_PACKET_SIZE];
static volatile uint32_t gPendingLength = 0U;
static volatile bool gTransmitPending = false;
static volatile bool gReceivePaused = false;
static uint8_t gLineCoding[7] = {0x00U, 0xC2U, 0x01U, 0x00U, 0U, 0U, 8U};
static uint8_t gDeviceDescriptor[] = {
    18U, USB_DESC_TYPE_DEVICE, 0x00U, 0x02U, 0x02U, 0x02U, 0U, 64U,
    0x83U, 0x04U, 0x40U, 0x57U, 0x00U, 0x01U, 1U, 2U, 3U, 1U
};
static uint8_t gLangDescriptor[] = {4U, USB_DESC_TYPE_STRING, 0x09U, 0x04U};
static uint8_t gStringDescriptor[USBD_MAX_STR_DESC_SIZ];

/** @brief Return the only CDC class storage without using the heap. */
void *drvUsbStaticAlloc(uint32_t size) {
    if (gAllocated || (size > sizeof(gCdcStorage))) {
        return NULL;
    }
    gAllocated = true;
    return &gCdcStorage;
}

/** @brief Release the static slot when the host resets or unconfigures CDC. */
void drvUsbStaticFree(void *memory) {
    if (memory == &gCdcStorage) {
        gAllocated = false;
    }
}

/** @brief Return the full-speed device descriptor. */
static uint8_t *drvUsbDeviceDescriptor(USBD_SpeedTypeDef speed, uint16_t *length) {
    (void)speed;
    *length = sizeof(gDeviceDescriptor);
    return gDeviceDescriptor;
}

/** @brief Select English USB strings. */
static uint8_t *drvUsbLangDescriptor(USBD_SpeedTypeDef speed, uint16_t *length) {
    (void)speed;
    *length = sizeof(gLangDescriptor);
    return gLangDescriptor;
}

/** @brief Convert a constant ASCII name to a USB string in ISR-owned storage. */
static uint8_t *drvUsbString(const char *text, uint16_t *length) {
    USBD_GetString((uint8_t *)text, gStringDescriptor, length);
    return gStringDescriptor;
}

/** @brief Report the development device manufacturer. */
static uint8_t *drvUsbManufacturer(USBD_SpeedTypeDef speed, uint16_t *length) {
    (void)speed;
    return drvUsbString("Heart-T", length);
}

/** @brief Report the virtual serial port product name. */
static uint8_t *drvUsbProduct(USBD_SpeedTypeDef speed, uint16_t *length) {
    (void)speed;
    return drvUsbString("Heart-T USB CDC", length);
}

/** @brief Build a stable per-MCU serial from all 96 unique-ID bits. */
static uint8_t *drvUsbSerial(USBD_SpeedTypeDef speed, uint16_t *length) {
    const char *lHex = "0123456789ABCDEF";
    const uint32_t *lUid = (const uint32_t *)UID_BASE;
    char lSerial[25];
    uint32_t lIndex;
    (void)speed;
    for (lIndex = 0U; lIndex < 24U; ++lIndex) {
        lSerial[lIndex] = lHex[(lUid[lIndex / 8U] >> (28U - 4U * (lIndex % 8U))) & 0xFU];
    }
    lSerial[24] = '\0';
    return drvUsbString(lSerial, length);
}

/** @brief Describe the single CDC configuration and interface. */
static uint8_t *drvUsbInterface(USBD_SpeedTypeDef speed, uint16_t *length) {
    (void)speed;
    return drvUsbString("CDC Echo", length);
}

static USBD_DescriptorsTypeDef gDescriptors = {
    drvUsbDeviceDescriptor, drvUsbLangDescriptor, drvUsbManufacturer,
    drvUsbProduct, drvUsbSerial, drvUsbInterface, drvUsbInterface
};

/** @brief Hand the packet buffer to CDC when configured, in USB ISR context. */
static int8_t drvUsbCdcInit(void) {
    gPendingLength = 0U;
    gTransmitPending = false;
    gReceivePaused = false;
    return (int8_t)USBD_CDC_SetRxBuffer(&gUsbDevice, gPacket);
}

/** @brief Drop session ownership on host reset/unconfigure, in USB ISR context. */
static int8_t drvUsbCdcDeInit(void) {
    gPendingLength = 0U;
    gTransmitPending = false;
    gReceivePaused = false;
    return (int8_t)USBD_OK;
}

/** @brief Store line coding; baud and DTR do not gate raw USB echo. */
static int8_t drvUsbCdcControl(uint8_t command, uint8_t *buffer, uint16_t length) {
    if ((command == CDC_SET_LINE_CODING) || (command == CDC_GET_LINE_CODING)) {
        if ((buffer == NULL) || (length != sizeof(gLineCoding))) {
            return (int8_t)USBD_FAIL;
        }
        if (command == CDC_SET_LINE_CODING) {
            memcpy(gLineCoding, buffer, sizeof(gLineCoding));
        } else {
            memcpy(buffer, gLineCoding, sizeof(gLineCoding));
        }
    }
    return (int8_t)USBD_OK;
}

/** @brief Publish one received packet; leave OUT NAK until its echo completes. */
static int8_t drvUsbCdcReceive(uint8_t *buffer, uint32_t *length) {
    if ((buffer != gPacket) || (length == NULL) || (*length > sizeof(gPacket))) {
        return (int8_t)USBD_FAIL;
    }
    gPendingLength = *length;
    gReceivePaused = true;
    return (int8_t)USBD_OK;
}

static USBD_CDC_ItfTypeDef gCdcInterface = {
    drvUsbCdcInit, drvUsbCdcDeInit, drvUsbCdcControl, drvUsbCdcReceive, NULL
};

/** @brief Force a host-visible disconnect before USB takes ownership of PA12. */
void drvUsbDisconnect(void) {
    GPIO_InitTypeDef lGpio = {0};
    __HAL_RCC_GPIOA_CLK_ENABLE();
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_12, GPIO_PIN_RESET);
    lGpio.Pin = GPIO_PIN_12;
    lGpio.Mode = GPIO_MODE_OUTPUT_PP;
    lGpio.Pull = GPIO_NOPULL;
    lGpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &lGpio);
    HAL_Delay(DRV_USB_DISCONNECT_MS);
    lGpio.Mode = GPIO_MODE_INPUT;
    HAL_GPIO_Init(GPIOA, &lGpio);
}

/** @brief Register CDC and enable USB interrupts only after device assembly. */
int8_t drvUsbInit(void) {
    if (gReady || (hpcd_USB_FS.Instance != USB) || (hpcd_USB_FS.State != HAL_PCD_STATE_READY)) {
        return DRV_USB_ERROR_STATE;
    }
    if ((USBD_Init(&gUsbDevice, &gDescriptors, 0U) != USBD_OK) ||
        (USBD_RegisterClass(&gUsbDevice, &USBD_CDC) != USBD_OK) ||
        (USBD_CDC_RegisterInterface(&gUsbDevice, &gCdcInterface) != USBD_OK) ||
        (USBD_Start(&gUsbDevice) != USBD_OK)) {
        (void)USBD_DeInit(&gUsbDevice);
        return DRV_USB_ERROR_TRANSFER;
    }
    gReady = true;
    HAL_NVIC_SetPriority(USB_LP_CAN1_RX0_IRQn, 3U, 0U);
    HAL_NVIC_EnableIRQ(USB_LP_CAN1_RX0_IRQn);
    return DRV_USB_OK;
}

/** @brief Echo one packet without waits, keeping its storage until IN/ZLP completion. */
int8_t drvUsbEchoProcess(void) {
    int8_t lStatus = DRV_USB_OK;
    USBD_CDC_HandleTypeDef *lCdc;
    if (!gReady) {
        return DRV_USB_ERROR_STATE;
    }
    /* Serialize CDC access with reset/receive interrupts; TIM2 and DRDY remain enabled. */
    HAL_NVIC_DisableIRQ(USB_LP_CAN1_RX0_IRQn);
    __DSB();
    __ISB();
    lCdc = (USBD_CDC_HandleTypeDef *)gUsbDevice.pClassData;
    if ((gUsbDevice.dev_state == USBD_STATE_CONFIGURED) && (lCdc != NULL)) {
        if (gTransmitPending && (lCdc->TxState == 0U)) {
            gTransmitPending = false;
        }
        if ((gPendingLength != 0U) && !gTransmitPending) {
            if ((USBD_CDC_SetTxBuffer(&gUsbDevice, gPacket, gPendingLength) == USBD_OK) &&
                (USBD_CDC_TransmitPacket(&gUsbDevice) == USBD_OK)) {
                gPendingLength = 0U;
                gTransmitPending = true;
            } else {
                lStatus = DRV_USB_ERROR_TRANSFER;
            }
        }
        if (gReceivePaused && !gTransmitPending && (gPendingLength == 0U)) {
            if (USBD_CDC_ReceivePacket(&gUsbDevice) == USBD_OK) {
                gReceivePaused = false;
            } else {
                lStatus = DRV_USB_ERROR_TRANSFER;
            }
        }
    }
    HAL_NVIC_EnableIRQ(USB_LP_CAN1_RX0_IRQn);
    return lStatus;
}
/**************************End of file********************************/

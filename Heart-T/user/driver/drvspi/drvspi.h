/************************************************************************************
* @file     : drvspi.h
* @brief    : SPI1 blocking transaction interface.
* @details  : Single main-loop owner; PA4 software CS, ADS1292R-compatible timing.
* @author   :
* @date     : 2026-09-17
* @version  : 1.0
* @copyright: Copyright (c) 2050
***********************************************************************************/
#ifndef USER_DRIVER_DRVSPI_H
#define USER_DRIVER_DRVSPI_H

#include <stdint.h>
#include "stm32g4xx_hal.h"

#ifdef __cplusplus
extern "C" {
#endif

#define DRV_SPI_OK                  1
#define DRV_SPI_ERROR_PARAM         (-10)
#define DRV_SPI_ERROR_STATE         (-11)
#define DRV_SPI_ERROR_TIMEOUT       (-12)
#define DRV_SPI_ERROR_TRANSFER      (-13)
#define DRV_SPI_CS_PORT             GPIOA
#define DRV_SPI_CS_PIN              GPIO_PIN_4
#define DRV_SPI_TIMEOUT_MS          20U
#define DRV_SPI_CS_HOLD_US          10U

/* Main-loop context only. Call after MX_DMA_Init and MX_SPI1_Init. */
int8_t drvSpiInit(void);
/* Full duplex, MSB first. Both buffers required, nonoverlapping, length in bytes.
 * CS stays low across the entire transfer and for >= 4 ADS1292R clock cycles.
 * The main loop owns SPI1; callers must serialize complete device operations. */
int8_t drvSpiTransfer(const uint8_t *tx, uint8_t *rx, uint16_t length);
/* Bounded hardware cycle delay; used for the shared PWDN/RESET pulse. */
void drvSpiDelayUs(uint32_t delayUs);

#ifdef __cplusplus
}
#endif
#endif /* USER_DRIVER_DRVSPI_H */
/**************************End of file********************************/

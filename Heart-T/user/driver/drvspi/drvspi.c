/************************************************************************************
* @file     : drvspi.c
* @brief    : SPI2 hardware transactions with software chip select.
* @details  : Mode 1, 8 bits, PCLK1 / 256; no allocation or ISR transfers.
* @author   :
* @date     : 2026-09-17
* @version  : 1.0
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "drvspi.h"
#include "spi.h"
#include <stdbool.h>
#include <stddef.h>

static bool gSpiReady = false;

/** @brief Wait using the Cortex-M3 cycle counter without changing SysTick. */
void drvSpiDelayUs(uint32_t delayUs) {
    uint32_t lStart = DWT->CYCCNT;
    uint32_t lCycles = ((SystemCoreClock + 999999U) / 1000000U) * delayUs;
    while ((uint32_t)(DWT->CYCCNT - lStart) < lCycles) {
        __NOP();
    }
}

/** @brief Verify CubeMX SPI configuration and prepare the cycle counter. */
int8_t drvSpiInit(void) {
    gSpiReady = false;
    if ((hspi2.Instance != SPI2) || (hspi2.State != HAL_SPI_STATE_READY) ||
        (hspi2.Init.Mode != SPI_MODE_MASTER) || (hspi2.Init.Direction != SPI_DIRECTION_2LINES) ||
        (hspi2.Init.DataSize != SPI_DATASIZE_8BIT) || (hspi2.Init.CLKPolarity != SPI_POLARITY_LOW) ||
        (hspi2.Init.CLKPhase != SPI_PHASE_2EDGE) || (hspi2.Init.NSS != SPI_NSS_SOFT) ||
        (hspi2.Init.FirstBit != SPI_FIRSTBIT_MSB) ||
        (hspi2.Init.BaudRatePrescaler != SPI_BAUDRATEPRESCALER_256)) {
        return DRV_SPI_ERROR_STATE;
    }
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    HAL_GPIO_WritePin(DRV_SPI_CS_PORT, DRV_SPI_CS_PIN, GPIO_PIN_SET);
    gSpiReady = true;
    return DRV_SPI_OK;
}

/** @brief Exchange one complete transaction and release CS on every exit. */
int8_t drvSpiTransfer(const uint8_t *tx, uint8_t *rx, uint16_t length) {
    HAL_StatusTypeDef lStatus;
    if ((tx == NULL) || (rx == NULL) || (length == 0U) || (tx == rx)) {
        return DRV_SPI_ERROR_PARAM;
    }
    if (!gSpiReady || (hspi2.State != HAL_SPI_STATE_READY)) {
        return DRV_SPI_ERROR_STATE;
    }
    HAL_GPIO_WritePin(DRV_SPI_CS_PORT, DRV_SPI_CS_PIN, GPIO_PIN_RESET);
    drvSpiDelayUs(1U);
    lStatus = HAL_SPI_TransmitReceive(&hspi2, (uint8_t *)tx, rx, length, DRV_SPI_TIMEOUT_MS);
    if (lStatus != HAL_OK) {
        (void)HAL_SPI_Abort(&hspi2);
    }
    drvSpiDelayUs(DRV_SPI_CS_HOLD_US);
    HAL_GPIO_WritePin(DRV_SPI_CS_PORT, DRV_SPI_CS_PIN, GPIO_PIN_SET);
    drvSpiDelayUs(1U);
    if (lStatus == HAL_TIMEOUT) {
        return DRV_SPI_ERROR_TIMEOUT;
    }
    return (lStatus == HAL_OK) ? DRV_SPI_OK : DRV_SPI_ERROR_TRANSFER;
}

/**************************End of file********************************/

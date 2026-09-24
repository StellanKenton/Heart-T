/************************************************************************************
* @file     : drvspi.h
* @brief    : ESP32-S3 ADS1292R SPI port.
* @details  : SPI mode 1 with one blocking owner.
***********************************************************************************/
#ifndef HEARTTHIRD_ESP_DRVSPI_H
#define HEARTTHIRD_ESP_DRVSPI_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define DRV_SPI_OK 1
#define DRV_SPI_ERROR_PARAM (-10)
#define DRV_SPI_ERROR_STATE (-11)
#define DRV_SPI_ERROR_TRANSFER (-13)
#define DRV_SPI_MISO_PIN 10
#define DRV_SPI_MOSI_PIN 11
#define DRV_SPI_SCLK_PIN 12
#define DRV_SPI_CS_PIN 13
#define DRV_SPI_CLOCK_HZ 1000000
int8_t drvSpiInit(void);
int8_t drvSpiTransfer(const uint8_t *tx, uint8_t *rx, uint16_t length);
void drvSpiDelayUs(uint32_t delayUs);
#ifdef __cplusplus
}
#endif
#endif
/**************************End of file********************************/

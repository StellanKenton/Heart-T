/************************************************************************************
* @file     : drvspi.c
* @brief    : ESP32-S3 GPIO and SPI binding for ADS1292R.
* @details  : SPI2 mode 1; software CS preserves the original transaction timing.
***********************************************************************************/
#include "drvspi.h"
#include "ads1292r.h"
#include "transport.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"
#include <stdbool.h>
#include <stddef.h>

static spi_device_handle_t gDevice;
static bool gReady;

/** @brief Count DRDY edges without performing a SPI transaction in interrupt context. */
static void drvSpiDrdyIsr(void *argument) {
    (void)argument;
    ads1292rDrdyIrq();
    transportDrdyIrq();
}

/** @brief Delay for short ADS1292R pin and chip-select timing. */
void drvSpiDelayUs(uint32_t delayUs) {
    esp_rom_delay_us(delayUs);
}

/** @brief Configure SPI and converter control pins once. */
int8_t drvSpiInit(void) {
    spi_bus_config_t lBus = {0};
    spi_device_interface_config_t lDevice = {0};
    gpio_config_t lPins = {0};
    if (gReady) {
        return DRV_SPI_OK;
    }
    lPins.pin_bit_mask = (1ULL << ADS1292R_START_PIN) | (1ULL << ADS1292R_PWDN_PIN) | (1ULL << DRV_SPI_CS_PIN);
    lPins.mode = GPIO_MODE_OUTPUT;
    if (gpio_config(&lPins) != ESP_OK) {
        return DRV_SPI_ERROR_STATE;
    }
    gpio_set_level(ADS1292R_START_PIN, 0);
    gpio_set_level(ADS1292R_PWDN_PIN, 0);
    gpio_set_level(DRV_SPI_CS_PIN, 1);
    lPins.pin_bit_mask = 1ULL << ADS1292R_DRDY_PIN;
    lPins.mode = GPIO_MODE_INPUT;
    lPins.intr_type = GPIO_INTR_NEGEDGE;
    if (gpio_config(&lPins) != ESP_OK || gpio_install_isr_service(0) != ESP_OK ||
        gpio_isr_handler_add(ADS1292R_DRDY_PIN, drvSpiDrdyIsr, NULL) != ESP_OK) {
        return DRV_SPI_ERROR_STATE;
    }
    lBus.miso_io_num = DRV_SPI_MISO_PIN;
    lBus.mosi_io_num = DRV_SPI_MOSI_PIN;
    lBus.sclk_io_num = DRV_SPI_SCLK_PIN;
    lBus.quadwp_io_num = -1;
    lBus.quadhd_io_num = -1;
    lBus.max_transfer_sz = 16;
    lDevice.clock_speed_hz = DRV_SPI_CLOCK_HZ;
    lDevice.mode = 1;
    lDevice.spics_io_num = -1;
    lDevice.queue_size = 1;
    if (spi_bus_initialize(SPI2_HOST, &lBus, SPI_DMA_DISABLED) != ESP_OK ||
        spi_bus_add_device(SPI2_HOST, &lDevice, &gDevice) != ESP_OK) {
        return DRV_SPI_ERROR_STATE;
    }
    gReady = true;
    return DRV_SPI_OK;
}

/** @brief Exchange a complete SPI transaction with a 10 us CS hold. */
int8_t drvSpiTransfer(const uint8_t *tx, uint8_t *rx, uint16_t length) {
    spi_transaction_t lTransaction = {0};
    esp_err_t lStatus;
    if (tx == NULL || rx == NULL || tx == rx || length == 0U) {
        return DRV_SPI_ERROR_PARAM;
    }
    if (!gReady) {
        return DRV_SPI_ERROR_STATE;
    }
    lTransaction.length = (size_t)length * 8U;
    lTransaction.tx_buffer = tx;
    lTransaction.rx_buffer = rx;
    gpio_set_level(DRV_SPI_CS_PIN, 0);
    drvSpiDelayUs(1U);
    lStatus = spi_device_polling_transmit(gDevice, &lTransaction);
    drvSpiDelayUs(10U);
    gpio_set_level(DRV_SPI_CS_PIN, 1);
    drvSpiDelayUs(1U);
    return lStatus == ESP_OK ? DRV_SPI_OK : DRV_SPI_ERROR_TRANSFER;
}
/**************************End of file********************************/

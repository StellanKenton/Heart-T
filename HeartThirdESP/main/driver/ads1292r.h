/************************************************************************************
* @file     : ads1292r.h
* @brief    : ADS1292R configuration and two-channel sample interface.
* @details  : Internal 512 kHz clock and 2.42 V reference; single main-loop owner.
* @author   :
* @date     : 2026-09-17
* @version  : 1.0
* @copyright: Copyright (c) 2050
***********************************************************************************/
#ifndef USER_DRIVER_ADS1292R_H
#define USER_DRIVER_ADS1292R_H

#include <stdbool.h>
#include <stdint.h>
#include "driver/gpio.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ADS1292R_OK                 1
#define ADS1292R_ERROR_PARAM        (-20)
#define ADS1292R_ERROR_STATE        (-21)
#define ADS1292R_ERROR_ID           (-22)
#define ADS1292R_ERROR_VERIFY       (-23)
#define ADS1292R_ERROR_NOT_READY    (-24)
#define ADS1292R_ERROR_FRAME        (-25)
#define ADS1292R_START_PIN          GPIO_NUM_16
#define ADS1292R_PWDN_PIN           GPIO_NUM_15
#define ADS1292R_DRDY_PIN           GPIO_NUM_17
#define ADS1292R_DEVICE_ID          0x73U
#define ADS1292_DEVICE_ID           0x53U
#define ADS1292R_REGISTER_COUNT     12U
#define ADS1292R_FRAME_BYTES        9U
#define ADS1292R_REG_ID             0x00U
#define ADS1292R_REG_CONFIG1        0x01U
#define ADS1292R_REG_CONFIG2        0x02U
#define ADS1292R_REG_LOFF           0x03U
#define ADS1292R_REG_CH1SET         0x04U
#define ADS1292R_REG_CH2SET         0x05U
#define ADS1292R_REG_RLD_SENS       0x06U
#define ADS1292R_REG_LOFF_SENS      0x07U
#define ADS1292R_REG_LOFF_STAT      0x08U
#define ADS1292R_REG_RESP1          0x09U
#define ADS1292R_REG_RESP2          0x0AU
#define ADS1292R_REG_GPIO           0x0BU
#define ADS1292R_CMD_SDATAC         0x11U
#define ADS1292R_CMD_RDATA          0x12U
#define ADS1292R_CMD_RREG           0x20U
#define ADS1292R_CMD_WREG           0x40U
#define ADS1292R_POWER_UP_MS        1000U
#define ADS1292R_REFERENCE_MS       200U
#define ADS1292R_RLD_OFF            0xC0U
#define ADS1292R_RLD_CH2            0xECU
#define ADS1292R_RLD_POWER          0x20U

typedef enum eAds1292rRate {
    ADS1292R_RATE_125 = 0, ADS1292R_RATE_250, ADS1292R_RATE_500,
    ADS1292R_RATE_1000, ADS1292R_RATE_2000, ADS1292R_RATE_4000, ADS1292R_RATE_8000
} eAds1292rRate;

typedef enum eAds1292rGain {
    ADS1292R_GAIN_6 = 0, ADS1292R_GAIN_1, ADS1292R_GAIN_2,
    ADS1292R_GAIN_3, ADS1292R_GAIN_4, ADS1292R_GAIN_8, ADS1292R_GAIN_12
} eAds1292rGain;

typedef enum eAds1292rInput {
    ADS1292R_INPUT_NORMAL = 0, ADS1292R_INPUT_SHORT = 1, ADS1292R_INPUT_TEST = 5
} eAds1292rInput;

typedef struct stAds1292rConfig {
    eAds1292rRate rate;
    eAds1292rGain gain[2];
    eAds1292rInput input[2];
    bool respiration;
    uint8_t respirationPhase; /* 0..15 in 11.25-degree steps, 32 kHz modulation. */
    bool leadOff;
    uint8_t rldSense; /* Default RLD off; both modes retain fMOD/4 PGA chopping. */
} stAds1292rConfig;

typedef struct stAds1292rSample {
    uint32_t status; /* 24 bits: 1100 + LOFF_STAT[4:0] + GPIO[1:0] + 13 zeros. */
    int32_t channel[2]; /* Sign-extended 24-bit ADC codes, not volts. */
    uint32_t sequence; /* DRDY edge counter; gaps indicate missed conversions. */
    uint32_t tickMs; /* Approximate main-loop read time. */
} stAds1292rSample;

typedef struct stAds1292rStats {
    uint32_t drdyCount;
    uint32_t sampleCount;
    uint32_t missedCount;
} stAds1292rStats;

/* Mutating and SPI APIs: main-loop only, after HAL initialization.
 * Init also powers up, resets, probes ID and verifies configuration; remains stopped. */
int8_t ads1292rLoadDefaultConfig(stAds1292rConfig *config);
int8_t ads1292rInit(const stAds1292rConfig *config);
int8_t ads1292rStart(void);
int8_t ads1292rStop(void);
int8_t ads1292rPowerDown(void);
/* Register access requires stopped conversions. Writes must preserve reserved bits,
 * continuous CONFIG1 operation and LOFF_STAT.CLK_DIV=0. Re-init after power down. */
int8_t ads1292rReadRegisters(uint8_t address, uint8_t *values, uint8_t count);
int8_t ads1292rWriteRegisters(uint8_t address, const uint8_t *values, uint8_t count);
/* Nonwaiting DRDY check followed by blocking RDATA transaction, no ISR SPI. */
int8_t ads1292rReadSample(stAds1292rSample *sample);
/* Read-only snapshots for the main loop; latest storage has no sample queue. */
int8_t ads1292rGetLatest(stAds1292rSample *sample);
int8_t ads1292rGetStats(stAds1292rStats *stats);
/* ISR only: called by the PB15 falling-edge EXTI handler. */
void ads1292rDrdyIrq(void);

#ifdef __cplusplus
}
#endif
#endif /* USER_DRIVER_ADS1292R_H */
/**************************End of file********************************/

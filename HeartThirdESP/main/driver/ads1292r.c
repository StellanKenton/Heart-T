/************************************************************************************
* @file     : ads1292r.c
* @brief    : ADS1292R power-up, register configuration and sample acquisition.
* @details  : SDATAC plus RDATA allows a read to span a subsequent DRDY edge.
* @author   :
* @date     : 2026-09-17
* @version  : 1.0
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "ads1292r.h"
#include "drvspi.h"
#include "system.h"
#include "log.h"
#include <stddef.h>
#include <string.h>

static bool gAwake = false;
static bool gInitialized = false;
static volatile bool gRunning = false;
static volatile uint32_t gDrdyCount = 0U;
static uint32_t gLastSequence = 0U;
static uint32_t gSampleCount = 0U;
static uint32_t gMissedCount = 0U;
static bool gLatestValid = false;
static stAds1292rSample gLatest;

/** @brief Send a single-byte opcode with full chip-select timing. */
static int8_t ads1292rCommand(uint8_t command) {
    uint8_t lRx;
    return drvSpiTransfer(&command, &lRx, 1U);
}

/** @brief Accept only electrode, shorted-input and internal-test mux settings. */
static bool ads1292rInputValid(eAds1292rInput input) {
    return (input == ADS1292R_INPUT_NORMAL) || (input == ADS1292R_INPUT_SHORT) || (input == ADS1292R_INPUT_TEST);
}

/** @brief Decode two's-complement without signed shifts or implementation-defined casts. */
static int32_t ads1292rDecode24(const uint8_t *bytes) {
    uint32_t lValue = ((uint32_t)bytes[0] << 16U) | ((uint32_t)bytes[1] << 8U) | bytes[2];
    return (lValue & 0x800000U) ? (int32_t)lValue - 0x1000000 : (int32_t)lValue;
}

/** @brief Load the default ECG configuration without driving hardware. */
int8_t ads1292rLoadDefaultConfig(stAds1292rConfig *config) {
    if (config == NULL) {
        return ADS1292R_ERROR_PARAM;
    }
    *config = (stAds1292rConfig){
        .rate = ADS1292R_RATE_500,
        .gain = {ADS1292R_GAIN_6, ADS1292R_GAIN_6},
        .input = {ADS1292R_INPUT_NORMAL, ADS1292R_INPUT_NORMAL},
        .respiration = false, .respirationPhase = 0U,
        .leadOff = false, .rldSense = 0xECU
    };
    return ADS1292R_OK;
}

/** @brief Read a contiguous register range while conversions are stopped. */
int8_t ads1292rReadRegisters(uint8_t address, uint8_t *values, uint8_t count) {
    uint8_t lTx[ADS1292R_REGISTER_COUNT + 2U] = {0};
    uint8_t lRx[ADS1292R_REGISTER_COUNT + 2U];
    int8_t lStatus;
    if ((values == NULL) || (count == 0U) || (address >= ADS1292R_REGISTER_COUNT) ||
        (count > ADS1292R_REGISTER_COUNT - address)) {
        return ADS1292R_ERROR_PARAM;
    }
    if (!gAwake || gRunning) {
        return ADS1292R_ERROR_STATE;
    }
    lTx[0] = ADS1292R_CMD_RREG | address;
    lTx[1] = count - 1U;
    lStatus = drvSpiTransfer(lTx, lRx, count + 2U);
    if (lStatus == DRV_SPI_OK) {
        memcpy(values, &lRx[2], count);
    }
    return lStatus;
}

/** @brief Write a contiguous range; the factory ID cannot be written. */
int8_t ads1292rWriteRegisters(uint8_t address, const uint8_t *values, uint8_t count) {
    uint8_t lTx[ADS1292R_REGISTER_COUNT + 2U];
    uint8_t lRx[ADS1292R_REGISTER_COUNT + 2U];
    uint8_t lIndex;
    if ((values == NULL) || (count == 0U) || (address == ADS1292R_REG_ID) ||
        (address >= ADS1292R_REGISTER_COUNT) || (count > ADS1292R_REGISTER_COUNT - address)) {
        return ADS1292R_ERROR_PARAM;
    }
    if (!gAwake || gRunning) {
        return ADS1292R_ERROR_STATE;
    }
    for (lIndex = 0U; lIndex < count; ++lIndex) {
        if (((address + lIndex == ADS1292R_REG_LOFF_STAT) && ((values[lIndex] & 0x40U) != 0U)) ||
            ((address + lIndex == ADS1292R_REG_CONFIG1) && ((values[lIndex] & 0xF8U) != 0U || (values[lIndex] & 7U) == 7U))) {
            return ADS1292R_ERROR_PARAM;
        }
    }
    lTx[0] = ADS1292R_CMD_WREG | address;
    lTx[1] = count - 1U;
    memcpy(&lTx[2], values, count);
    return drvSpiTransfer(lTx, lRx, count + 2U);
}

/** @brief Probe and configure the device; shut it down on any partial failure. */
int8_t ads1292rInit(const stAds1292rConfig *config) {
    uint8_t lRegs[ADS1292R_REGISTER_COUNT - 1U] = {
        0x02U, 0xA0U, 0x10U, 0x00U, 0x00U, 0x00U, 0x00U, 0x00U, 0x02U, 0x03U, 0x0CU
    };
    uint8_t lReadback[ADS1292R_REGISTER_COUNT - 1U];
    uint8_t lId;
    uint8_t lIndex;
    uint8_t lMask;
    int8_t lStatus;

    if ((config == NULL) || ((unsigned)config->rate > ADS1292R_RATE_8000) ||
        ((unsigned)config->gain[0] > ADS1292R_GAIN_12) || ((unsigned)config->gain[1] > ADS1292R_GAIN_12) ||
        !ads1292rInputValid(config->input[0]) || !ads1292rInputValid(config->input[1]) ||
        (config->respirationPhase > 15U) || (config->respiration &&
        ((config->input[0] != ADS1292R_INPUT_NORMAL) || (config->input[1] != ADS1292R_INPUT_NORMAL)))) {
        return ADS1292R_ERROR_PARAM;
    }
    if (gRunning) {
        return ADS1292R_ERROR_STATE;
    }
    gAwake = false;
    gInitialized = false;
    gLatestValid = false;
    lStatus = drvSpiInit();
    if (lStatus != DRV_SPI_OK) {
        return lStatus;
    }
    gpio_set_level(ADS1292R_START_PIN, 0);
    gpio_set_level(ADS1292R_PWDN_PIN, 1);
    lStatus = systemDelayMs(ADS1292R_POWER_UP_MS);
    if (lStatus != SYSTEM_OK) {
        goto fail;
    }
    /* Short reset pulse, not the > 4 ms power-down pulse. */
    gpio_set_level(ADS1292R_PWDN_PIN, 0);
    drvSpiDelayUs(100U);
    gpio_set_level(ADS1292R_PWDN_PIN, 1);
    lStatus = systemDelayMs(2U); /* At least 18 tCLK after reset release. */
    if (lStatus != SYSTEM_OK) {
        goto fail;
    }
    gAwake = true;
    lStatus = ads1292rCommand(ADS1292R_CMD_SDATAC);
    if (lStatus != ADS1292R_OK) {
        goto fail;
    }
    lStatus = ads1292rReadRegisters(ADS1292R_REG_ID, &lId, 1U);
    if (lStatus != ADS1292R_OK) {
        goto fail;
    }
    LOG_I("ads1292r", "probe ID=0x%02X", (unsigned)lId);
    if ((lId != ADS1292R_DEVICE_ID) && (lId != ADS1292_DEVICE_ID)) {
        LOG_E("ads1292r", "invalid ID; check SPI/power/CLKSEL; DRDY=%u START=%u PWDN=%u",
              (unsigned)gpio_get_level(ADS1292R_DRDY_PIN),
              (unsigned)gpio_get_level(ADS1292R_START_PIN),
              (unsigned)gpio_get_level(ADS1292R_PWDN_PIN));
        lStatus = ADS1292R_ERROR_ID;
        goto fail;
    }
    if (config->respiration && (lId != ADS1292R_DEVICE_ID)) {
        LOG_E("ads1292r", "respiration requires ADS1292R");
        lStatus = ADS1292R_ERROR_PARAM;
        goto fail;
    }
    lRegs[0] = (uint8_t)config->rate;
    if (config->leadOff) {
        lRegs[1] |= 0x40U;
        lRegs[6] = 0x0FU;
    }
    if ((config->input[0] == ADS1292R_INPUT_TEST) || (config->input[1] == ADS1292R_INPUT_TEST)) {
        lRegs[1] |= 0x03U; /* Internal 1 Hz square wave. */
    }
    lRegs[3] = ((uint8_t)config->gain[0] << 4U) | (uint8_t)config->input[0];
    lRegs[4] = ((uint8_t)config->gain[1] << 4U) | (uint8_t)config->input[1];
    lRegs[5] = config->rldSense;
    if (config->respiration) {
        lRegs[8] = 0xC2U | (config->respirationPhase << 2U);
    }
    lStatus = ads1292rWriteRegisters(ADS1292R_REG_CONFIG1, lRegs, sizeof(lRegs));
    if (lStatus != ADS1292R_OK) {
        goto fail;
    }
    lStatus = ads1292rReadRegisters(ADS1292R_REG_CONFIG1, lReadback, sizeof(lReadback));
    if (lStatus != ADS1292R_OK) {
        goto fail;
    }
    for (lIndex = 0U; lIndex < sizeof(lRegs); ++lIndex) {
        /* Lead-off and GPIO input levels are live, not writable storage. */
        lMask = (lIndex == 7U) ? 0x40U : ((lIndex == 10U) ? 0x0CU : 0xFFU);
        if ((lReadback[lIndex] & lMask) != (lRegs[lIndex] & lMask)) {
            LOG_E("ads1292r", "reg=0x%02X expected=0x%02X actual=0x%02X mask=0x%02X",
                  (unsigned)(lIndex + 1U), (unsigned)lRegs[lIndex],
                  (unsigned)lReadback[lIndex], (unsigned)lMask);
            lStatus = ADS1292R_ERROR_VERIFY;
            goto fail;
        }
    }
    lStatus = systemDelayMs(ADS1292R_REFERENCE_MS);
    if (lStatus != SYSTEM_OK) {
        goto fail;
    }
    gInitialized = true;
    LOG_I("ads1292r", "register readback verified; reference settled");
    return ADS1292R_OK;

fail:
    gpio_set_level(ADS1292R_PWDN_PIN, 0);
    gAwake = false;
    return lStatus;
}

/** @brief Start a new capture session and clear sample counters. */
int8_t ads1292rStart(void) {
    if (!gInitialized || !gAwake || gRunning) {
        return ADS1292R_ERROR_STATE;
    }
    gDrdyCount = 0U;
    gLastSequence = 0U;
    gSampleCount = 0U;
    gMissedCount = 0U;
    gLatestValid = false;
    gRunning = true;
    gpio_set_level(ADS1292R_START_PIN, 1);
    return ADS1292R_OK;
}

/** @brief Stop through START, then allow the converter stop timing to elapse. */
int8_t ads1292rStop(void) {
    if (!gInitialized || !gAwake) {
        return ADS1292R_ERROR_STATE;
    }
    gpio_set_level(ADS1292R_START_PIN, 0);
    drvSpiDelayUs(100U); /* >= 8 tMOD with a 512 kHz master clock. */
    gRunning = false;
    return ADS1292R_OK;
}

/** @brief Hold PWDN low; initialization is mandatory before the next start. */
int8_t ads1292rPowerDown(void) {
    gpio_set_level(ADS1292R_START_PIN, 0);
    gRunning = false;
    gpio_set_level(ADS1292R_PWDN_PIN, 0);
    gAwake = false;
    gInitialized = false;
    gLatestValid = false;
    return systemDelayMs(6U);
}

/** @brief Record an edge only; acquisition stays in main-loop context. */
void ads1292rDrdyIrq(void) {
    if (gRunning) {
        ++gDrdyCount;
    }
}

/** @brief Read status plus two channels and publish a coherent latest snapshot. */
int8_t ads1292rReadSample(stAds1292rSample *sample) {
    uint8_t lTx[ADS1292R_FRAME_BYTES + 1U] = {ADS1292R_CMD_RDATA};
    uint8_t lRx[ADS1292R_FRAME_BYTES + 1U];
    stAds1292rSample lSample;
    uint32_t lGap;
    int8_t lStatus;
    if (sample == NULL) {
        return ADS1292R_ERROR_PARAM;
    }
    if (!gRunning) {
        return ADS1292R_ERROR_STATE;
    }
    if (gpio_get_level(ADS1292R_DRDY_PIN) != 0) {
        return ADS1292R_ERROR_NOT_READY;
    }
    lSample.sequence = gDrdyCount;
    lSample.tickMs = systemGetTickMs();
    lStatus = drvSpiTransfer(lTx, lRx, sizeof(lTx));
    if (lStatus != ADS1292R_OK) {
        return lStatus;
    }
    lSample.status = ((uint32_t)lRx[1] << 16U) | ((uint32_t)lRx[2] << 8U) | lRx[3];
    if ((lSample.status & 0xF00000U) != 0xC00000U) {
        return ADS1292R_ERROR_FRAME;
    }
    lSample.channel[0] = ads1292rDecode24(&lRx[4]);
    lSample.channel[1] = ads1292rDecode24(&lRx[7]);
    lGap = lSample.sequence - gLastSequence;
    gLastSequence = lSample.sequence;
    if (lGap > 1U) {
        gMissedCount += lGap - 1U;
    }
    ++gSampleCount;
    gLatest = lSample;
    gLatestValid = true;
    *sample = lSample;
    return ADS1292R_OK;
}

/** @brief Copy the latest successful acquisition from the main loop. */
int8_t ads1292rGetLatest(stAds1292rSample *sample) {
    int8_t lStatus = ADS1292R_ERROR_NOT_READY;
    if (sample == NULL) {
        return ADS1292R_ERROR_PARAM;
    }
    if (gLatestValid) {
        *sample = gLatest;
        lStatus = ADS1292R_OK;
    }
    return lStatus;
}

/** @brief Copy diagnostic counters; edge gaps provide an overrun estimate. */
int8_t ads1292rGetStats(stAds1292rStats *stats) {
    if (stats == NULL) {
        return ADS1292R_ERROR_PARAM;
    }
    stats->drdyCount = gDrdyCount;
    stats->sampleCount = gSampleCount;
    stats->missedCount = gMissedCount;
    return ADS1292R_OK;
}

/**************************End of file********************************/

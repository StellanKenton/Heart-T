/************************************************************************************
* @file     : taskmanager.c
* @brief    : Bare-metal sensor, communication, algorithm and background functions.
* @details  : TIM2 deadlines dispatch cooperative main-loop work.
* @author   :
* @date     : 2026-09-17
* @version  : 2.0
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "taskmanager.h"
#include "system.h"
#include "log.h"
#include "ads1292r.h"
#include "drvusb.h"
#include <stdbool.h>
#include <stddef.h>

static bool gSensorReady = false;
static bool gUsbReady = false;
static uint32_t gLastUsbErrorMs = 0U;
static stAds1292rSample gSensorSample;
static uint32_t gLastReportMs = 0U;
static uint32_t gLastSampleCount = 0U;
static uint32_t gLastErrorMs = 0U;
static stPeriodicFunction gFunctions[] = {
    {sensorProcess, SENSOR_INTERVAL_MS, 0U},
    {communicationProcess, COMMUNICATION_INTERVAL_MS, 0U},
    {algoProcess, ALGO_INTERVAL_MS, 0U},
    {backgroundProcess, BACKGROUND_INTERVAL_MS, 0U},
};

/** @brief Configure hardware once before cooperative dispatch begins. */
void taskManagerInit(void) {
    stAds1292rConfig lConfig;
    int8_t lStatus;
    uint32_t lNowMs;
    size_t lIndex;

    lStatus = drvUsbInit();
    gUsbReady = (lStatus == DRV_USB_OK);
    if (gUsbReady) {
        LOG_I("usb", "CDC sample stream ready");
    } else {
        LOG_E("usb", "init failed status=%d", (int)lStatus);
    }

    (void)ads1292rLoadDefaultConfig(&lConfig);
    lStatus = ads1292rInit(&lConfig);
    if (lStatus == ADS1292R_OK) {
        lStatus = ads1292rStart();
    }
    gSensorReady = (lStatus == ADS1292R_OK);
    if (gSensorReady) {
        (void)systemSetMode(E_SYSTEM_NORMAL_MODE);
        LOG_I("ads1292r", "500 SPS, gain=6, ECG capture started");
    } else {
        (void)systemSetMode(E_SYSTEM_FAULT_MODE);
        LOG_E("ads1292r", "init/start failed status=%d; console remains available", (int)lStatus);
    }
    lNowMs = systemGetTickMs();
    gLastReportMs = lNowMs;
    gLastErrorMs = lNowMs - SENSOR_REPORT_INTERVAL_MS;
    gLastSampleCount = 0U;
    for (lIndex = 0U; lIndex < sizeof(gFunctions) / sizeof(gFunctions[0]); ++lIndex) {
        gFunctions[lIndex].lastRunMs = lNowMs;
    }
    LOG_I("main", "bare-metal periodic functions ready");
    (void)logFlush();
}

/** @brief Run each due function once, with no blocking scheduler or catch-up loop. */
void taskManagerProcess(void) {
    size_t lIndex;
    uint32_t lNowMs;
    for (lIndex = 0U; lIndex < sizeof(gFunctions) / sizeof(gFunctions[0]); ++lIndex) {
        lNowMs = systemGetTickMs();
        if ((uint32_t)(lNowMs - gFunctions[lIndex].lastRunMs) >= gFunctions[lIndex].intervalMs) {
            gFunctions[lIndex].lastRunMs = lNowMs;
            gFunctions[lIndex].process();
        }
    }
}

/** @brief Acquire at most one DRDY sample without millisecond waits. */
void sensorProcess(void) {
    int8_t lStatus;
    uint32_t lNowMs;
    if (!gSensorReady) {
        return;
    }
    lStatus = ads1292rReadSample(&gSensorSample);
    if (lStatus == ADS1292R_OK) {
        drvUsbQueueSample(gSensorSample.channel);
    }
    if ((lStatus != ADS1292R_OK) && (lStatus != ADS1292R_ERROR_NOT_READY)) {
        lNowMs = systemGetTickMs();
        if ((uint32_t)(lNowMs - gLastErrorMs) >= SENSOR_REPORT_INTERVAL_MS) {
            gLastErrorMs = lNowMs;
            LOG_E("ads1292r", "sample failed status=%d", (int)lStatus);
        }
    }
}

/** @brief Process one communication iteration. */
void communicationProcess(void) {
    int8_t lStatus;
    uint32_t lNowMs;
    if (!gUsbReady) {
        return;
    }
    lStatus = drvUsbStreamProcess();
    lNowMs = systemGetTickMs();
    if ((lStatus != DRV_USB_OK) && ((uint32_t)(lNowMs - gLastUsbErrorMs) >= SENSOR_REPORT_INTERVAL_MS)) {
        gLastUsbErrorMs = lNowMs;
        LOG_E("usb", "stream failed status=%d", (int)lStatus);
    }
}

/** @brief Process one algorithm iteration using the latest sensor data. */
void algoProcess(void) {
    /* Read ads1292rGetLatest() here when the ECG algorithm is implemented. */
}

/** @brief Service logging and report acquisition status at one-second intervals. */
void backgroundProcess(void) {
    stAds1292rStats lStats;
    uint32_t lNowMs = systemGetTickMs();
    if (gSensorReady && ((uint32_t)(lNowMs - gLastReportMs) >= SENSOR_REPORT_INTERVAL_MS)) {
        gLastReportMs = lNowMs;
        (void)ads1292rGetStats(&lStats);
        if (lStats.sampleCount == gLastSampleCount) {
            LOG_W("ads1292r", "no new samples; check DRDY PB15 and CLKSEL");
        } else {
            LOG_I("ads1292r", "samples=%lu missed=%lu usb_dropped=%lu ch1=%ld ch2=%ld",
                  (unsigned long)lStats.sampleCount, (unsigned long)lStats.missedCount,
                  (unsigned long)drvUsbGetDroppedSamples(),
                  (long)gSensorSample.channel[0], (long)gSensorSample.channel[1]);
        }
        gLastSampleCount = lStats.sampleCount;
    }
    (void)logProcess((uint16_t)BACKGROUND_INTERVAL_MS);
}
/**************************End of file********************************/

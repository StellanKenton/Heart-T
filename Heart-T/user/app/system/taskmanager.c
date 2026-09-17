/************************************************************************************
* @file     : taskmanager.c
* @brief    : HeartThird worker task assembly.
* @details  : Creates sensor, communication, algorithm and background tasks.
* @author   :
* @date     :
* @version  :
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "taskmanager.h"

#include <stdbool.h>
#include <stddef.h>
#include "rtos.h"
#include "log.h"
#include "ads1292r.h"

static bool gWorkerTasksCreated = false;
static repRtosTaskHandle gSensorTaskHandle = NULL;
static repRtosTaskHandle gCommunicationTaskHandle = NULL;
static repRtosTaskHandle gAlgoTaskHandle = NULL;
static repRtosTaskHandle gBackGroudTaskHandle = NULL;

static void sensorTask(void *argument);
static void communicationTask(void *argument);
static void algoTask(void *argument);
static void backGroudTask(void *argument);

static const stRepRtosTaskConfig gWorkerTaskConfigs[] = {
    {"SensorTask", sensorTask, NULL, SENSOR_TASK_STACK_SIZE, SENSOR_TASK_PRIORITY, &gSensorTaskHandle},
    {"CommunicationTask", communicationTask, NULL, COMMUNICATION_TASK_STACK_SIZE, COMMUNICATION_TASK_PRIORITY, &gCommunicationTaskHandle},
    {"AlgoTask", algoTask, NULL, ALGO_TASK_STACK_SIZE, ALGO_TASK_PRIORITY, &gAlgoTaskHandle},
    {"BackGroudTask", backGroudTask, NULL, BACKGROUD_TASK_STACK_SIZE, BACKGROUD_TASK_PRIORITY, &gBackGroudTaskHandle},
};

/** @brief Own sensor initialization and periodic sample acquisition. */
static void sensorTask(void *argument) {
    stAds1292rConfig lConfig;
    stAds1292rSample lSample = {0};
    stAds1292rStats lStats;
    uint32_t lPreviousWakeMs;
    uint32_t lLastReportMs;
    uint32_t lLastSampleCount = 0U;
    uint32_t lNowMs;
    int8_t lStatus;
    (void)argument;

    (void)ads1292rLoadDefaultConfig(&lConfig);
    for (;;) {
        lStatus = ads1292rInit(&lConfig);
        if (lStatus == ADS1292R_OK) {
            lStatus = ads1292rStart();
        }
        if (lStatus == ADS1292R_OK) {
            break;
        }
        LOG_E("ads1292r", "init/start failed status=%d", (int)lStatus);
        (void)repRtosTaskDelayMs(1000U);
    }
    LOG_I("ads1292r", "ID=0x73, 500 SPS, gain=6, ECG capture started");
    lPreviousWakeMs = repRtosGetTickMs();
    lLastReportMs = lPreviousWakeMs;
    for (;;) {
        lStatus = ads1292rReadSample(&lSample);
        if ((lStatus != ADS1292R_OK) && (lStatus != ADS1292R_ERROR_NOT_READY)) {
            LOG_E("ads1292r", "sample failed status=%d", (int)lStatus);
            /* Bound error logging and bus retries when wiring is faulty. */
            (void)repRtosTaskDelayMs(100U);
            lPreviousWakeMs = repRtosGetTickMs();
        }
        lNowMs = repRtosGetTickMs();
        if ((uint32_t)(lNowMs - lLastReportMs) >= 1000U) {
            (void)ads1292rGetStats(&lStats);
            if (lStats.sampleCount == lLastSampleCount) {
                LOG_W("ads1292r", "no new samples; check DRDY PB15 and CLKSEL");
            } else {
                LOG_I("ads1292r", "samples=%lu missed=%lu ch1=%ld ch2=%ld",
                      (unsigned long)lStats.sampleCount, (unsigned long)lStats.missedCount,
                      (long)lSample.channel[0], (long)lSample.channel[1]);
            }
            lLastSampleCount = lStats.sampleCount;
            lLastReportMs = lNowMs;
        }
        (void)repRtosTaskDelayUntilMs(&lPreviousWakeMs, SENSOR_TASK_INTERVAL_MS);
    }
}

/** @brief Own communication transport and protocol processing. */
static void communicationTask(void *argument) {
    uint32_t lPreviousWakeMs = repRtosGetTickMs();
    (void)argument;

    for (;;) {
        /* TODO: Process HeartThird receive/transmit and protocol messages. */
        (void)repRtosTaskDelayUntilMs(&lPreviousWakeMs, COMMUNICATION_TASK_INTERVAL_MS);
    }
}

/** @brief Process completed sensor samples with the HeartThird algorithms. */
static void algoTask(void *argument) {
    uint32_t lPreviousWakeMs = repRtosGetTickMs();
    (void)argument;

    for (;;) {
        /* Read ads1292rGetLatest() here when the ECG algorithm is implemented. */
        (void)repRtosTaskDelayUntilMs(&lPreviousWakeMs, ALGO_TASK_INTERVAL_MS);
    }
}

/** @brief Run low-priority system maintenance. */
static void backGroudTask(void *argument) {
    uint32_t lPreviousWakeMs = repRtosGetTickMs();
    (void)argument;

    LOG_I("taskManager", "BackGroudTask started; RTT console ready");

    for (;;) {
        (void)logProcess((uint16_t)BACKGROUD_TASK_INTERVAL_MS);
        (void)repRtosTaskDelayUntilMs(&lPreviousWakeMs, BACKGROUD_TASK_INTERVAL_MS);
    }
}

/** @brief Register all workers before scheduling; roll back a partial failure. */
int8_t taskManagerRegister(void) {
    size_t lIndex;
    int8_t lStatus;

    if (gWorkerTasksCreated) {
        return REP_RTOS_STATUS_OK;
    }

    for (lIndex = 0U; lIndex < sizeof(gWorkerTaskConfigs) / sizeof(gWorkerTaskConfigs[0]); ++lIndex) {
        lStatus = repRtosTaskCreate(&gWorkerTaskConfigs[lIndex]);
        if (lStatus != REP_RTOS_STATUS_OK) {
            LOG_E("taskManager", "create failed: %s status=%d", gWorkerTaskConfigs[lIndex].name, (int)lStatus);
            while (lIndex > 0U) {
                --lIndex;
                repRtosTaskDelete(*gWorkerTaskConfigs[lIndex].handle);
                *gWorkerTaskConfigs[lIndex].handle = NULL;
            }
            return lStatus;
        }
    }

    gWorkerTasksCreated = true;
    LOG_I("taskManager", "registered SensorTask, CommunicationTask, AlgoTask, BackGroudTask");
    return REP_RTOS_STATUS_OK;
}

/**************************End of file********************************/

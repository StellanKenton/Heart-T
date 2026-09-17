/************************************************************************************
* @file     : taskmanager.h
* @brief    : Bare-metal periodic function scheduler.
* @details  : Periods are milliseconds from the TIM6 clock.
* @author   :
* @date     : 2026-09-17
* @version  : 2.0
* @copyright: Copyright (c) 2050
***********************************************************************************/
#ifndef HEARTTHIRD_TASK_MANAGER_H
#define HEARTTHIRD_TASK_MANAGER_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define SENSOR_INTERVAL_MS          1U
#define COMMUNICATION_INTERVAL_MS   10U
#define ALGO_INTERVAL_MS            10U
#define BACKGROUND_INTERVAL_MS      20U
#define SENSOR_REPORT_INTERVAL_MS   1000U

typedef void (*pfPeriodicFunction)(void);
typedef struct stPeriodicFunction {
    pfPeriodicFunction process;
    uint32_t intervalMs;
    uint32_t lastRunMs;
} stPeriodicFunction;

/* Startup initializes the sensor once; failure leaves the console available. */
void taskManagerInit(void);
/* Call continuously from main. Overdue functions run once; missed periods are skipped.
 * Unsigned time differences handle the millisecond counter wrapping. */
void taskManagerProcess(void);
/* Main-loop only: each function performs one bounded iteration and returns. */
void sensorProcess(void);
void communicationProcess(void);
void algoProcess(void);
void backgroundProcess(void);
#ifdef __cplusplus
}
#endif
#endif /* HEARTTHIRD_TASK_MANAGER_H */
/**************************End of file********************************/

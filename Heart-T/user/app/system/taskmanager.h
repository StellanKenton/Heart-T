/************************************************************************************
* @file     : taskmanager.h
* @brief    : HeartThird worker task configuration.
* @details  : Stack sizes are in 32-bit words; larger priorities run first.
* @author   :
* @date     :
* @version  :
* @copyright: Copyright (c) 2050
***********************************************************************************/
#ifndef HEARTTHIRD_TASK_MANAGER_H
#define HEARTTHIRD_TASK_MANAGER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Initial budgets for task skeletons; measure stack usage when adding work. */
#define SENSOR_TASK_STACK_SIZE          256U
#define SENSOR_TASK_PRIORITY            4U
#define SENSOR_TASK_INTERVAL_MS         1U

#define COMMUNICATION_TASK_STACK_SIZE   128U
#define COMMUNICATION_TASK_PRIORITY     3U
#define COMMUNICATION_TASK_INTERVAL_MS  10U

#define ALGO_TASK_STACK_SIZE            128U
#define ALGO_TASK_PRIORITY              2U
#define ALGO_TASK_INTERVAL_MS           10U

#define BACKGROUD_TASK_STACK_SIZE       512U
#define BACKGROUD_TASK_PRIORITY         1U
#define BACKGROUD_TASK_INTERVAL_MS      20U

/* Call after kernel initialization and before scheduler start, never from ISR.
 * Repeated successful calls are harmless. Failure removes tasks from this attempt.
 * Returns REP_RTOS_STATUS_OK or the task creation error from rtos.h.
 */
int8_t taskManagerRegister(void);

#ifdef __cplusplus
}
#endif

#endif /* HEARTTHIRD_TASK_MANAGER_H */

/**************************End of file********************************/

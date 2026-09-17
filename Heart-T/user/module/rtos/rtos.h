/************************************************************************************
* @file     : rtos.h
* @brief    : Project RTOS abstraction.
* @details  : Exposes only the task and scheduler operations used by the project.
* @author   :
* @date     :
* @version  :
* @copyright: Copyright (c) 2050
***********************************************************************************/
#ifndef USER_MODULE_RTOS_H
#define USER_MODULE_RTOS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REP_RTOS_STATUS_OK               1
#define REP_RTOS_STATUS_INVALID_PARAM    (-1)
#define REP_RTOS_STATUS_NOT_READY        (-2)
#define REP_RTOS_STATUS_ERROR            (-3)

typedef void (*pfRepRtosTaskEntry)(void *argument);
typedef void *repRtosTaskHandle;

typedef struct stRepRtosTaskConfig {
    const char *name;
    pfRepRtosTaskEntry entry;
    void *argument;
    /* Stack depth in 32-bit words; priority increases with its numeric value. */
    uint32_t stackSize;
    uint32_t priority;
    repRtosTaskHandle *handle;
} stRepRtosTaskConfig;

typedef struct stRepRtosOps {
    int8_t (*taskCreate)(const stRepRtosTaskConfig *config);
    void (*taskDelete)(repRtosTaskHandle handle);
    int8_t (*taskDelayMs)(uint32_t delayMs);
    int8_t (*taskDelayUntilMs)(uint32_t *previousWakeMs, uint32_t periodMs);
    uint32_t (*getTickMs)(void);
    void (*enterCritical)(void);
    void (*exitCritical)(void);
    int8_t (*schedulerInit)(void);
    int8_t (*schedulerStart)(void);
} stRepRtosOps;

/* Task APIs are task-context only. Creation is also allowed before scheduler start. */
int8_t repRtosTaskCreate(const stRepRtosTaskConfig *config);
/* A NULL handle deletes the calling task. Deleted handles must not be reused. */
void repRtosTaskDelete(repRtosTaskHandle handle);
/* Zero milliseconds yields to another ready task at the same priority. */
int8_t repRtosTaskDelayMs(uint32_t delayMs);

/**
 * @brief Block a task until the next absolute periodic wake time.
 * @param previousWakeMs Previous absolute wake time in milliseconds; updated on return.
 * @param periodMs Task period in milliseconds.
 * @return REP_RTOS_STATUS_OK on success, otherwise a negative error code.
 */
int8_t repRtosTaskDelayUntilMs(uint32_t *previousWakeMs, uint32_t periodMs);
/* May be read from a task or ISR; wraps at UINT32_MAX milliseconds at 1 kHz. */
uint32_t repRtosGetTickMs(void);
/* Task-context only; calls must be paired and may be nested. */
void repRtosEnterCritical(void);
void repRtosExitCritical(void);
/* Initialize once before creating tasks. Successful start does not return. */
int8_t repRtosSchedulerInit(void);
int8_t repRtosSchedulerStart(void);

#ifdef __cplusplus
}
#endif

#endif /* USER_MODULE_RTOS_H */
/**************************End of file********************************/

/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * File Name          : app_freertos.c
  * Description        : Code for freertos applications
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* USER CODE BEGIN Includes */
#include "rtos.h"
#include "system.h"
#include "taskmanager.h"
#include "log.h"
/* USER CODE END Includes */

void MX_FREERTOS_Init(void);

/**
 * @brief Initialize HeartThird state and register its workers before scheduler start.
 */
void MX_FREERTOS_Init(void) {
    /* USER CODE BEGIN Init */
    systemInit();
    if (taskManagerRegister() != REP_RTOS_STATUS_OK) {
        (void)systemSetMode(E_SYSTEM_FAULT_MODE);
        (void)logFlush();
        Error_Handler();
    }
    /* Stay in standby until the HeartThird acquisition pipeline is implemented. */
    (void)systemSetMode(E_SYSTEM_STANDBY_MODE);
    /* USER CODE END Init */
}

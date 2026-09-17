/************************************************************************************
* @file     : venttest.h
* @brief    : Ventilation test console command.
* @details  : Declares ventilation test commands and incremental transient logging.
* @author   :
* @date     :
* @version  :
* @copyright: Copyright (c) 2050
***********************************************************************************/
#ifndef VENTTEST_H
#define VENTTEST_H

#include <stdbool.h>
#include <stdint.h>

#define VENT_TEST_TRANSIENT_SAMPLE_INTERVAL_MS  6U
#define VENT_TEST_TRANSIENT_DURATION_MS         1000U
#define VENT_TEST_TRANSIENT_SAMPLE_COUNT        ((VENT_TEST_TRANSIENT_DURATION_MS + \
                                                  VENT_TEST_TRANSIENT_SAMPLE_INTERVAL_MS - 1U) / \
                                                 VENT_TEST_TRANSIENT_SAMPLE_INTERVAL_MS)

#ifdef __cplusplus
extern "C" {
#endif

bool ventTestConsoleRegister(void);
void ventTestTransientRecord(void);

#ifdef __cplusplus
}
#endif

#endif /* VENTTEST_H */
/**************************End of file********************************/

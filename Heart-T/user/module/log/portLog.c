/************************************************************************************
* @file     : portLog.c
* @brief    : Logging port implementation.
* @details  : Selects the MCU run-time provider according to the log configuration.
* @author   :
* @date     :
* @version  :
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "portLog.h"

#include <stddef.h>

#include "system.h"

static const stPortLogOps gPortLogDefaultOps = {
    .getRunTimeMs = systemGetTickMs,
};
static const stPortLogOps *gPortLogBoardOps = &gPortLogDefaultOps;

bool portLogRegisterOps(const stPortLogOps *ops)
{
    if ((ops == NULL) || (ops->getRunTimeMs == NULL)) {
        return false;
    }

    gPortLogBoardOps = ops;
    return true;
}

const stPortLogOps *portLogGetOps(void)
{
    return gPortLogBoardOps;
}

uint32_t portLogGetRunTimeMs(void)
{
    const stPortLogOps *lOps = portLogGetOps();

    if ((lOps == NULL) || (lOps->getRunTimeMs == NULL)) {
        return 0U;
    }

    return lOps->getRunTimeMs();
}

/**************************End of file********************************/

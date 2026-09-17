/************************************************************************************
* @file     : sysdebug.c
* @brief    : System debug console command implementation.
* @details  : Provides MCU reboot and run-time query commands.
* @author   :
* @date     :
* @version  :
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "sysdebug.h"

#include "console.h"
#include "stm32g4xx.h"
#include "log.h"
#include "system.h"

/** @brief Flush the reboot message and reset the HeartThird MCU. */
static eConsoleCommandResult sysdebugConsoleReboot(const char *arguments) {
    if (arguments[0] != '\0') {
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    LOG_I("sysdebug", "rebooting HeartThird");
    (void)logFlush();
    NVIC_SystemReset();
    return CONSOLE_COMMAND_RESULT_OK;
}

/** @brief Report uptime using the TIM6 millisecond clock. */
static eConsoleCommandResult sysdebugConsoleTime(const char *arguments) {
    if (arguments[0] != '\0') {
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    LOG_I("sysdebug", "runtime %lu ms", (unsigned long)systemGetTickMs());
    return CONSOLE_COMMAND_RESULT_OK;
}

/** @brief List all commands bound during startup. */
static eConsoleCommandResult sysdebugConsoleHelp(const char *arguments) {
    if (arguments[0] != '\0') {
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    consoleShowHelp();
    return CONSOLE_COMMAND_RESULT_OK;
}

/** @brief Report HeartThird firmware and hardware information. */
static eConsoleCommandResult sysdebugConsoleVersion(const char *arguments) {
    if (arguments[0] != '\0') {
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    LOG_I("sysdebug", "%s firmware=%s hardware=%s", systemGetFirmwareName(),
          systemGetFirmwareVersion(), systemGetHardwareVersion());
    return CONSOLE_COMMAND_RESULT_OK;
}

/** @brief Report the current application state without starting acquisition. */
static eConsoleCommandResult sysdebugConsoleStatus(const char *arguments) {
    if (arguments[0] != '\0') {
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    LOG_I("sysdebug", "mode=%s uptime=%lu ms", systemGetModeString(systemGetMode()),
          (unsigned long)systemGetTickMs());
    return CONSOLE_COMMAND_RESULT_OK;
}

static const stConsoleCommand gSysdebugConsoleCommands[] = {
    {"reboot", "Restart HeartThird", sysdebugConsoleReboot},
    {"time", "Show uptime in milliseconds", sysdebugConsoleTime},
    {"help", "Show all registered commands", sysdebugConsoleHelp},
    {"version", "Show firmware and hardware versions", sysdebugConsoleVersion},
    {"status", "Show system mode and uptime", sysdebugConsoleStatus},
};

/** @brief Bind the static HeartThird descriptors during startup. */
bool sysdebugConsoleRegister(void) {
    uint32_t lIndex;

    for (lIndex = 0U; lIndex < sizeof(gSysdebugConsoleCommands) / sizeof(gSysdebugConsoleCommands[0]); ++lIndex) {
        if (!consoleRegisterCommand(&gSysdebugConsoleCommands[lIndex])) {
            return false;
        }
    }
    return true;
}

/**************************End of file********************************/

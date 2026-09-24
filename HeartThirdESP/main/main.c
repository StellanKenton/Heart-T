/************************************************************************************
* @file     : main.c
* @brief    : ESP32-S3 firmware assembly and TCP console commands.
* @details  : ADS1292R acquisition, Wi-Fi and both TCP services start at boot.
***********************************************************************************/
#include "ads1292r.h"
#include "console.h"
#include "log.h"
#include "system.h"
#include "transport.h"
#include "esp_system.h"
#include <string.h>

/** @brief Restart the MCU after reporting the command. */
static eConsoleCommandResult mainReboot(const char *arguments) {
    if (arguments[0] != '\0') {
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    LOG_I("sysdebug", "rebooting HeartThirdESP");
    transportFlushLogs();
    (void)systemDelayMs(100U);
    esp_restart();
    return CONSOLE_COMMAND_RESULT_OK;
}

/** @brief Report uptime from the ESP timer. */
static eConsoleCommandResult mainTime(const char *arguments) {
    if (arguments[0] != '\0') {
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    LOG_I("sysdebug", "runtime %lu ms", (unsigned long)systemGetTickMs());
    return CONSOLE_COMMAND_RESULT_OK;
}

/** @brief List registered console commands. */
static eConsoleCommandResult mainHelp(const char *arguments) {
    if (arguments[0] != '\0') {
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    consoleShowHelp();
    return CONSOLE_COMMAND_RESULT_OK;
}

/** @brief Report firmware and board versions. */
static eConsoleCommandResult mainVersion(const char *arguments) {
    if (arguments[0] != '\0') {
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    LOG_I("sysdebug", "%s firmware=%s hardware=%s", FIRMWARE_NAME, FIRMWARE_VERSION, HARDWARE_VERSION);
    return CONSOLE_COMMAND_RESULT_OK;
}

/** @brief Report Wi-Fi, ADC counters and TCP queue loss. */
static eConsoleCommandResult mainStatus(const char *arguments) {
    stAds1292rStats lStats;
    char lIp[16];
    if (arguments[0] != '\0') {
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    (void)ads1292rGetStats(&lStats);
    transportGetIp(lIp, sizeof(lIp));
    LOG_I("sysdebug", "mode=%s wifi=%s ip=%s uptime=%lu ms samples=%lu missed=%lu tcp_dropped=%lu",
          transportSensorMode(), transportWifiConnected() ? "connected" : "disconnected", lIp[0] ? lIp : "none",
          (unsigned long)systemGetTickMs(), (unsigned long)lStats.sampleCount,
          (unsigned long)lStats.missedCount, (unsigned long)transportDroppedSamples());
    LOG_I("sysdebug", "rld=%s RLD_SENS=0x%02X breath=%s",
          strcmp(transportSensorMode(), "NORMAL") == 0 ?
              ((transportRldSense() & ADS1292R_RLD_POWER) != 0U ? "on" : "off") : "unavailable",
          (unsigned)transportRldSense(),
          transportBreathEnabled() ? "on" : "off");
    return CONSOLE_COMMAND_RESULT_OK;
}

/** @brief Request respiration carrier switching in the sole ADS owner task. */
static eConsoleCommandResult mainBreath(const char *arguments) {
    bool lEnabled;
    if (strcmp(arguments, "on") == 0) {
        lEnabled = true;
    } else if (strcmp(arguments, "off") == 0) {
        lEnabled = false;
    } else {
        LOG_W("sysdebug", "usage: breath on|off");
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    if (!transportSetBreath(lEnabled)) {
        LOG_E("sysdebug", "breath request failed; sensor unavailable");
        return CONSOLE_COMMAND_RESULT_ERROR;
    }
    LOG_I("sysdebug", "breath %s requested", lEnabled ? "on" : "off");
    return CONSOLE_COMMAND_RESULT_OK;
}

/** @brief Request RLD switching without changing PGA chopping or channel gains. */
static eConsoleCommandResult mainRld(const char *arguments) {
    bool lEnabled;
    if (strcmp(arguments, "on") == 0) {
        lEnabled = true;
    } else if (strcmp(arguments, "off") == 0) {
        lEnabled = false;
    } else {
        LOG_W("sysdebug", "usage: rld on|off");
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }
    if (!transportSetRld(lEnabled)) {
        LOG_E("sysdebug", "rld request failed; sensor unavailable or request queue full");
        return CONSOLE_COMMAND_RESULT_ERROR;
    }
    LOG_I("sysdebug", "rld %s requested", lEnabled ? "on" : "off");
    return CONSOLE_COMMAND_RESULT_OK;
}

static const stConsoleCommand gCommands[] = {
    {"reboot", "Restart HeartThirdESP", mainReboot},
    {"time", "Show uptime in milliseconds", mainTime},
    {"help", "List commands", mainHelp},
    {"version", "Show firmware and hardware versions", mainVersion},
    {"status", "Show Wi-Fi and acquisition counters", mainStatus},
    {"breath", "Enable or disable CH1 respiration carrier: breath on|off", mainBreath},
    {"rld", "Enable or disable CH2 right leg drive: rld on|off", mainRld},
};

/** @brief Initialize logging and command handlers before network tasks run. */
void app_main(void) {
    uint32_t lIndex;
    if (!logInit()) {
        return;
    }
    consoleInit();
    for (lIndex = 0U; lIndex < sizeof(gCommands) / sizeof(gCommands[0]); ++lIndex) {
        if (!consoleRegisterCommand(&gCommands[lIndex])) {
            LOG_E("main", "console registration failed");
            return;
        }
    }
    LOG_I("main", "%s firmware=%s hardware=%s boot", FIRMWARE_NAME, FIRMWARE_VERSION, HARDWARE_VERSION);
    if (!transportStart()) {
        LOG_E("main", "transport initialization failed");
    }
}
/**************************End of file********************************/

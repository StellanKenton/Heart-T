/************************************************************************************
* @file     : venttest.c
* @brief    : Ventilation test console command implementation.
* @details  : Provides direct ventilation mode and running-state test controls.
* @author   :
* @date     :
* @version  :
* @copyright: Copyright (c) 2050
***********************************************************************************/
#include "venttest.h"

#include <stdint.h>
#include <stddef.h>

#include "apneaengine.h"
#include "breathscheduler.h"
#include "calibtrans.h"
#include "console.h"
#include "log.h"
#include "monitordata.h"
#include "monitorengine.h"
#include "controldata.h"
#include "phasecontroller.h"
#include "system.h"

static const char *const gVentTestTag = "venttest";
static stMonitorWaveformData gVentTestTransientBuffer[VENT_TEST_TRANSIENT_SAMPLE_COUNT];
static stMonitorWaveformData gVentTestTransientUpload[VENT_TEST_TRANSIENT_SAMPLE_COUNT];
static volatile uint32_t gVentTestTransientTotalCount = 0U;
static uint32_t gVentTestTransientUploadedCount = 0U;

/** Convert a signal to a log-friendly hundredth-unit integer. */
static int32_t ventTestCenti(float value)
{
    return (int32_t)(value * 100.0F);
}

/** Skip spaces in the command arguments. */
static const char *ventTestSkipSpaces(const char *arguments)
{
    while ((*arguments == ' ') || (*arguments == '\t')) {
        arguments++;
    }

    return arguments;
}

/** Match one token and require a token boundary. */
static bool ventTestTokenMatch(const char **arguments, const char *expected)
{
    const char *lArgument = ventTestSkipSpaces(*arguments);
    uint32_t lIndex = 0U;

    while (expected[lIndex] != '\0') {
        if (lArgument[lIndex] != expected[lIndex]) {
            return false;
        }
        lIndex++;
    }
    if ((lArgument[lIndex] != '\0') && (lArgument[lIndex] != ' ') && (lArgument[lIndex] != '\t')) {
        return false;
    }

    *arguments = lArgument + lIndex;
    return true;
}

/** Parse one unsigned decimal test argument. */
static bool ventTestUnsignedParse(const char **arguments, uint16_t *value)
{
    const char *lArgument = ventTestSkipSpaces(*arguments);
    uint32_t lValue = 0U;
    uint8_t lDigitFound = 0U;

    while ((lArgument[0] >= '0') && (lArgument[0] <= '9')) {
        lDigitFound = 1U;
        lValue = (lValue * 10U) + (uint32_t)(lArgument[0] - '0');
        if (lValue > UINT16_MAX) {
            return false;
        }
        lArgument++;
    }
    if ((lDigitFound == 0U) ||
        ((lArgument[0] != '\0') && (lArgument[0] != ' ') && (lArgument[0] != '\t'))) {
        return false;
    }

    *arguments = lArgument;
    *value = (uint16_t)lValue;
    return true;
}

/** Show the supported ventilation test commands. */
static void ventTestUsageShow(void)
{
    LOG_I(gVentTestTag, "usage: vt mode <x> | run <0|1> | pac | vac | prvc | prvcsimv | vs | bapap | aprv | psv | psvst | psimv | vsimv | stop | set <peep> <delta> [ti_ms rate rise_ms] | support <peep> <delta> | volume <peep> <ml> [pause_pct [ti_ms rate]] | trigger off | trigger pressure <cmh2o100> | trigger flow <lpm100> | peep | status");
}

/** Report selected settings and the active breath separately. */
static void ventTestSettingsShow(void) {
    stVentPacSettings lPac;
    stVentCpapPsvSettings lSettings;
    stVentPsvStSettings lStSettings;
    stBreathPlan lPlan;
    uint8_t lHost;
    int8_t lStatus;
    lPac = *GetVentPacSettings();
    lSettings = *GetVentCpapPsvSettings();
    lStSettings = *GetVentPsvStSettings();
    lHost = GetVentPatientSettings()->useHostSettings;
    lStatus = phaseControllerActivePlanGet(&lPlan);
    LOG_R("VT_PAC_SETTINGS,peep100=%ld,delta100=%ld,rate100=%ld,ti_ms=%lu,rise_ms=%lu",
          (long)ventTestCenti(lPac.peep), (long)ventTestCenti(lPac.DeltaPressure),
          (long)ventTestCenti(lPac.Rate), (unsigned long)lPac.inspiratoryTimeMs,
          (unsigned long)lPac.riseTimeMs);
    LOG_R("VT_PSV_SETTINGS,host=%u,peep100=%ld,support100=%ld,backup100=%ld",
          (unsigned int)lHost, (long)ventTestCenti(lSettings.peepCmh2o),
          (long)ventTestCenti(lSettings.pressureSupportCmh2o),
          (long)ventTestCenti(lSettings.apneaPressureCmh2o));
    LOG_R("VT_PSVST_SETTINGS,host=%u,peep100=%ld,support100=%ld,rate100=%ld,ti_ms=%lu,max_ti_ms=%lu,rise_ms=%lu,cycle100=%ld",
          (unsigned int)lHost, (long)ventTestCenti(lStSettings.peepCmh2o),
          (long)ventTestCenti(lStSettings.pressureSupportCmh2o),
          (long)ventTestCenti(lStSettings.inspRateBpm),
          (unsigned long)lStSettings.inspTimeMs,
          (unsigned long)lStSettings.maxInspiratoryTimeMs,
          (unsigned long)lStSettings.riseTimeMs,
          (long)ventTestCenti(lStSettings.cycleOffPercent));
    if (lStatus == PHASE_CONTROL_SUCCESS) {
        LOG_R("VT_ACTIVE_PLAN,mode=%u,type=%u,trigger=%u,sequence=%lu,peep100=%ld,target100=%ld,low100=%ld",
              (unsigned int)lPlan.mode, (unsigned int)lPlan.breathType,
              (unsigned int)lPlan.triggerReason, (unsigned long)lPlan.sequence,
              (long)ventTestCenti(lPlan.peepCmh2o),
              (long)ventTestCenti(lPlan.inspiratoryPressureCmh2o),
              (long)ventTestCenti(lPlan.limitSettings->pressureLow));
    }
}

/** Snapshot display timing without uploading the waveform buffer. */
static void ventTestPeepShow(void) {
    stBreathPlan lPlan = {0};
    uint32_t lNowMs;
    ePhaseControllerState lPhase;
    uint8_t lReady;
    float lPressure;
    float lDynamic;
    float lDisplay;
    float lValid;

    lNowMs = systemGetTickMs();
    (void)phaseControllerActivePlanGet(&lPlan);
    lPhase = phaseControllerStateGet();
    lReady = phaseControllerExpirationReadyGet();
    lPressure = controlDataGet(PAT_REAL_PRS);
    lDynamic = monitorEngineGet(MONITOR_DYN_PEEP);
    lDisplay = monitorEngineGet(MONITOR_HMI_PEEP);
    lValid = monitorEngineGet(MONITOR_HMI_PEEP_VALID);
    LOG_R("VT_PEEP,time_ms=%lu,sequence=%lu,mode=%u,phase=%u,ready=%u,pressure100=%ld,dynamic100=%ld,display100=%ld,valid=%u",
          (unsigned long)lNowMs, (unsigned long)lPlan.sequence,
          (unsigned int)lPlan.mode, (unsigned int)lPhase, (unsigned int)lReady,
          (long)ventTestCenti(lPressure), (long)ventTestCenti(lDynamic),
          (long)ventTestCenti(lDisplay), (unsigned int)(lValid != 0.0F));
}

/** Upload only samples recorded since the previous status command. */
static void ventTestStatusShow(void)
{
    stBreathResult lBreathResult;
    stBreathPlan lPlan;
    float lBlowerLimit;
    uint32_t lCurrentCount;
    uint32_t lDroppedCount = 0U;
    uint32_t lFirstSequence;
    uint32_t lSequence;
    uint16_t lCount;
    uint16_t lIndex;

    lCurrentCount = gVentTestTransientTotalCount;
    lFirstSequence = gVentTestTransientUploadedCount;
    if ((lCurrentCount - lFirstSequence) > VENT_TEST_TRANSIENT_SAMPLE_COUNT) {
        lDroppedCount = (lCurrentCount - lFirstSequence) - VENT_TEST_TRANSIENT_SAMPLE_COUNT;
        lFirstSequence = lCurrentCount - VENT_TEST_TRANSIENT_SAMPLE_COUNT;
    }
    lCount = (uint16_t)(lCurrentCount - lFirstSequence);
    for (lIndex = 0U; lIndex < lCount; lIndex++) {
        lSequence = lFirstSequence + lIndex;
        gVentTestTransientUpload[lIndex] = gVentTestTransientBuffer[lSequence % VENT_TEST_TRANSIENT_SAMPLE_COUNT];
    }
    gVentTestTransientUploadedCount = lCurrentCount;

    /* Report the applied plan, so a pressure-limited tail is not mistaken for pause. */
    if ((phaseControllerActivePlanGet(&lPlan) == PHASE_CONTROL_SUCCESS) &&
        (lPlan.breathType == BREATH_TYPE_MANDATORY_VOLUME) &&
        (lPlan.limitSettings != NULL) &&
        (calibtransPrsSpeed(lPlan.limitSettings->pressureHigh, &lBlowerLimit) ==
         CALIBTRANS_STATUS_OK)) {
        LOG_R("VT_VOLUME_PLAN,flow100=%ld,delivery_ms=%lu,pause_ms=%lu,pressure_limit100=%ld,blower_limit100=%ld",
              (long)ventTestCenti(lPlan.inspiratoryFlowLpm),
              (unsigned long)lPlan.riseTimeMs, (unsigned long)lPlan.holdTimeMs,
              (long)ventTestCenti(lPlan.limitSettings->pressureHigh),
              (long)ventTestCenti(lBlowerLimit));
        LOG_R("VT_VOLUME_FEEDBACK,sequence=%lu,target100=%ld,filtered_vti100=%ld,correction100=%ld,delivery_target100=%ld",
              (unsigned long)lPlan.sequence,
              (long)ventTestCenti(lPlan.targetTidalVolumeMl),
              (long)ventTestCenti(lPlan.filteredVtiMl),
              (long)ventTestCenti(lPlan.volumeCorrectionMl),
              (long)ventTestCenti(lPlan.deliveryTargetMl));
    }
    if (monitorEngineBreathResultGet(&lBreathResult) == MONITOR_ENGINE_SUCCESS) {
        LOG_R("VT_BREATH_RESULT,sequence=%lu,mode=%u,type=%u,trigger=%u,cycle_reason=%u,vti100=%ld,vte100=%ld,ppeak100=%ld,pplat100=%ld,peep100=%ld,peak_insp_flow100=%ld,ti_ms=%lu,cycle_ms=%lu,valid=0x%08lX",
              (unsigned long)lBreathResult.sequence,
              (unsigned int)lBreathResult.mode,
              (unsigned int)lBreathResult.breathType,
              (unsigned int)lBreathResult.triggerReason,
              (unsigned int)lBreathResult.cycleReason,
              (long)ventTestCenti(lBreathResult.vtiMl),
              (long)ventTestCenti(lBreathResult.vteMl),
              (long)ventTestCenti(lBreathResult.ppeakCmh2o),
              (long)ventTestCenti(lBreathResult.plateauPressureCmh2o),
              (long)ventTestCenti(lBreathResult.peepCmh2o),
              (long)ventTestCenti(lBreathResult.peakInspiratoryFlowLpm),
              (unsigned long)lBreathResult.inspiratoryTimeMs,
              (unsigned long)lBreathResult.cycleTimeMs,
              (unsigned long)lBreathResult.validMask);
    }
    LOG_R("VT_APNEA_STATE,state=%u", (unsigned int)apneaEngineStateGet());
    LOG_R("VT_TRANSIENT_BEGIN,count=%u,interval_ms=%u,first_sequence=%lu,dropped=%lu",
          (unsigned int)lCount,
          (unsigned int)VENT_TEST_TRANSIENT_SAMPLE_INTERVAL_MS,
          (unsigned long)lFirstSequence,
          (unsigned long)lDroppedCount);
    LOG_R("VT_MONITOR_SCALE,float_fields=100");
    LOG_R("sequence,time_ms,air_x2,o2_x2,prox_x2,pinsp_x1,ppeep_x1,pexp_x1,ppat_x1,blower_x10,pref_x1,flowcomp_x1,pcorr_x1,effort_x1,ff_x1,vt_x10,vti_x10,vte_x10,target_x100,valve_x2,expiration_state,pressure_state,volume_pause,pause_settled,leak_lpm,flow_ref_lpm,flow_measurement_lpm,flow_effort,flow_blower_ff");
    for (lIndex = 0U; lIndex < lCount; lIndex++) {
        const stMonitorWaveformData *lSample = &gVentTestTransientUpload[lIndex];

        lSequence = lFirstSequence + lIndex;
        LOG_R("%lu,%lu,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%u,%u,%u,%u,%u,%u,%ld,%ld,%ld,%ld,%ld",
              (unsigned long)lSequence,
              (unsigned long)(lSequence * VENT_TEST_TRANSIENT_SAMPLE_INTERVAL_MS),
              (long)ventTestCenti(lSample->airFlowX2),
              (long)ventTestCenti(lSample->oxygenFlowX2),
              (long)ventTestCenti(lSample->proximalFlowX2),
              (long)ventTestCenti(lSample->inspPressureX1),
              (long)ventTestCenti(lSample->peepPressureX1),
              (long)ventTestCenti(lSample->expPressureX1),
              (long)ventTestCenti(lSample->patientPressureX1),
              (long)ventTestCenti(lSample->blowerSpeedX10),
              (long)ventTestCenti(lSample->patientRefPressureX1),
              (long)ventTestCenti(lSample->flowCompensationX1),
              (long)ventTestCenti(lSample->patientCorrectionX1),
              (long)ventTestCenti(lSample->innerEffortX1),
              (long)ventTestCenti(lSample->blowerFeedforwardX1),
              (long)ventTestCenti(lSample->tidalVolumeX10),
              (long)ventTestCenti(lSample->tidalVolumeInspX10),
              (long)ventTestCenti(lSample->tidalVolumeExpX10),
              (unsigned int)lSample->blowerTargetX100,
              (unsigned int)lSample->valveDutyX2,
              (unsigned int)lSample->expirationControllerState,
              (unsigned int)lSample->pressureControllerState,
              (unsigned int)lSample->volumePauseActive,
              (unsigned int)lSample->volumePauseSettled,
              (long)ventTestCenti(lSample->leakFlowLpm),
              (long)ventTestCenti(lSample->flowReferenceLpm),
              (long)ventTestCenti(lSample->flowMeasurementLpm),
              (long)ventTestCenti(lSample->flowEffort),
              (long)ventTestCenti(lSample->flowBlowerFeedforward));
    }
    LOG_R("VT_TRANSIENT_END,count=%u", (unsigned int)lCount);
}

/** Record one control-cycle sample into the rolling one-second buffer. */
void ventTestTransientRecord(void)
{
    uint32_t lSequence = gVentTestTransientTotalCount;

    gVentTestTransientBuffer[lSequence % VENT_TEST_TRANSIENT_SAMPLE_COUNT] =
        gMonitorWaveformData;
    gVentTestTransientTotalCount = lSequence + 1U;
}

/** Dispatch a ventilation test command. */
static eConsoleCommandResult ventTestConsoleCommand(const char *arguments)
{
    stVentPacSettings lPreviousSettings;
    stVentVacSettings lPreviousVacSettings;
    stVentCpapPsvSettings lPreviousCpapPsvSettings;
    stVentPsvStSettings lPreviousPsvStSettings;
    stVentPacSettings *lPacSettings;
    stVentVacSettings *lVacSettings;
    stVentCpapPsvSettings *lCpapPsvSettings;
    stVentPsvStSettings *lPsvStSettings;
    int8_t lStatus;
    uint16_t lDeltaPressure;
    uint16_t lRiseMs;
    uint16_t lMode;
    uint16_t lPeep;
    uint16_t lTidalVolume;
    uint16_t lPausePct;
    uint16_t lInspTimeMs;
    uint16_t lRate;
    uint16_t lTriggerThreshold;
    uint8_t lRun;
    eVentTriggerType lTriggerType;
    eVentMode lConfiguredMode;

    if (ventTestTokenMatch(&arguments, "pac") &&
        (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_PAC);
        LOG_I(gVentTestTag, "PAC start status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "vac") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_VAC);
        LOG_I(gVentTestTag, "VAC start status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "prvc") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_PRVC);
        LOG_I(gVentTestTag, "PRVC start status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "prvcsimv") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_PRVC_SIMV);
        LOG_I(gVentTestTag, "PRVC-SIMV start status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "vs") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_VS);
        LOG_I(gVentTestTag, "VS start status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "bapap") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_BAPAP);
        LOG_I(gVentTestTag, "BAPAP start status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "aprv") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_APRV);
        LOG_I(gVentTestTag, "APRV start status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "psimv") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_P_SIMV);
        LOG_I(gVentTestTag, "P-SIMV start status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "vsimv") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_V_SIMV);
        LOG_I(gVentTestTag, "V-SIMV start status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "psv") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_CPAP_PSV);
        LOG_I(gVentTestTag, "PSV start status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "psvst") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerStart(VENT_MD_PSV_ST);
        LOG_I(gVentTestTag, "PSV-ST start status=%d", (int)lStatus);
        ventTestSettingsShow();
    } else if (ventTestTokenMatch(&arguments, "stop") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerTestRunSet(0U);
        LOG_I(gVentTestTag, "stop status=%d", (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "peep") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        ventTestPeepShow();
        return CONSOLE_COMMAND_RESULT_OK;
    } else if (ventTestTokenMatch(&arguments, "status") &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        ventTestSettingsShow();
        ventTestStatusShow();
        return CONSOLE_COMMAND_RESULT_OK;
    } else if (ventTestTokenMatch(&arguments, "support") &&
               ventTestUnsignedParse(&arguments, &lPeep) &&
               ventTestUnsignedParse(&arguments, &lDeltaPressure) &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        (void)breathSchedulerStop();
        lCpapPsvSettings = GetVentCpapPsvSettings();
        lPreviousCpapPsvSettings = *lCpapPsvSettings;
        lCpapPsvSettings->peepCmh2o = (float)lPeep;
        lCpapPsvSettings->pressureSupportCmh2o = (float)lDeltaPressure;
        lStatus = breathSchedulerTestModeSet((uint8_t)VENT_MD_CPAP_PSV);
        if (lStatus != BREATH_CONTROL_SUCCESS) {
            *lCpapPsvSettings = lPreviousCpapPsvSettings;
            (void)breathSchedulerTestModeSet((uint8_t)VENT_MD_CPAP_PSV);
        }
        LOG_I(gVentTestTag, "support peep=%u delta=%u status=%d",
              (unsigned int)lPeep, (unsigned int)lDeltaPressure, (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "set") &&
               ventTestUnsignedParse(&arguments, &lPeep) &&
               ventTestUnsignedParse(&arguments, &lDeltaPressure)) {
        lPacSettings = GetVentPacSettings();
        lInspTimeMs = (uint16_t)lPacSettings->inspiratoryTimeMs;
        lRate = (uint16_t)lPacSettings->Rate;
        lRiseMs = (uint16_t)lPacSettings->riseTimeMs;
        if ((*ventTestSkipSpaces(arguments) != '\0') &&
            (!ventTestUnsignedParse(&arguments, &lInspTimeMs) ||
             !ventTestUnsignedParse(&arguments, &lRate) ||
             !ventTestUnsignedParse(&arguments, &lRiseMs))) {
            return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
        }
        if ((*ventTestSkipSpaces(arguments) != '\0') || (lRate == 0U) ||
            (lRate < GetVentLimitSettings()->frequencyLow) ||
            (lRate > GetVentLimitSettings()->frequencyHigh) ||
            (lInspTimeMs == 0U) || (lRiseMs > lInspTimeMs) ||
            ((uint32_t)lInspTimeMs + BREATH_PEEP_LOCK_TIME_MS > 60000U / lRate)) {
            return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
        }
        (void)breathSchedulerStop();
        lPreviousSettings = *lPacSettings;
        lPacSettings->peep = (float)lPeep;
        lPacSettings->DeltaPressure = (float)lDeltaPressure;
        lPacSettings->inspiratoryTimeMs = lInspTimeMs;
        lPacSettings->Rate = (float)lRate;
        lPacSettings->riseTimeMs = lRiseMs;
        lStatus = breathSchedulerTestModeSet((uint8_t)VENT_MD_PAC);
        if (lStatus != BREATH_CONTROL_SUCCESS) {
            *lPacSettings = lPreviousSettings;
            (void)breathSchedulerTestModeSet((uint8_t)VENT_MD_PAC);
        }
        LOG_I(gVentTestTag,
              "set peep100=%u delta100=%u target100=%u status=%d",
              (unsigned int)(lPeep * 100U),
              (unsigned int)(lDeltaPressure * 100U),
              (unsigned int)((lPeep + lDeltaPressure) * 100U),
              (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "volume") &&
               ventTestUnsignedParse(&arguments, &lPeep) &&
               ventTestUnsignedParse(&arguments, &lTidalVolume)) {
        /* An omitted pause preserves the current setting; zero is explicit. */
        lPausePct = (uint16_t)GetVentVacSettings()->inspPausePct;
        lInspTimeMs = (uint16_t)GetVentVacSettings()->inspTimeMs;
        lRate = (uint16_t)GetVentVacSettings()->freq;
        if ((*ventTestSkipSpaces(arguments) != '\0') &&
            !ventTestUnsignedParse(&arguments, &lPausePct)) {
            return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
        }
        /* Optional Ti and rate are supplied together after the pause percentage. */
        if ((*ventTestSkipSpaces(arguments) != '\0') &&
            (!ventTestUnsignedParse(&arguments, &lInspTimeMs) ||
             !ventTestUnsignedParse(&arguments, &lRate))) {
            return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
        }
        if ((*ventTestSkipSpaces(arguments) != '\0') || (lPausePct >= 100U) ||
            (lRate < GetVentLimitSettings()->frequencyLow) ||
            (lRate > GetVentLimitSettings()->frequencyHigh) ||
            (lInspTimeMs == 0U) ||
            ((uint32_t)lInspTimeMs + BREATH_PEEP_LOCK_TIME_MS > 60000U / lRate)) {
            return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
        }
        if (((float)lPeep < GetVentLimitSettings()->pressureLow) ||
            ((float)lPeep >= GetVentLimitSettings()->pressureHigh) ||
            (lTidalVolume < GetVentLimitSettings()->tidalVolumeLow) ||
            (lTidalVolume > GetVentLimitSettings()->tidalVolumeHigh)) {
            return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
        }
        (void)breathSchedulerStop();
        lVacSettings = GetVentVacSettings();
        lPreviousVacSettings = *lVacSettings;
        lVacSettings->peep = (float)lPeep;
        lVacSettings->tidalVolume = (float)lTidalVolume;
        lVacSettings->inspPausePct = (float)lPausePct;
        lVacSettings->inspTimeMs = lInspTimeMs;
        lVacSettings->freq = (float)lRate;
        lStatus = breathSchedulerTestModeSet((uint8_t)VENT_MD_VAC);
        if (lStatus != BREATH_CONTROL_SUCCESS) {
            *lVacSettings = lPreviousVacSettings;
            (void)breathSchedulerTestModeSet((uint8_t)VENT_MD_VAC);
        }
        LOG_I(gVentTestTag, "volume peep=%u ml=%u ti_ms=%u pause_pct=%u rate=%u status=%d",
              (unsigned int)lPeep, (unsigned int)lTidalVolume,
              (unsigned int)lVacSettings->inspTimeMs,
              (unsigned int)lVacSettings->inspPausePct,
              (unsigned int)lVacSettings->freq, (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "trigger")) {
        if (ventTestTokenMatch(&arguments, "off") &&
            (*ventTestSkipSpaces(arguments) == '\0')) {
            lTriggerType = VENT_TRIGGER_OFF;
            lTriggerThreshold = 0U;
        } else if (ventTestTokenMatch(&arguments, "pressure") &&
                   ventTestUnsignedParse(&arguments, &lTriggerThreshold) &&
                   (lTriggerThreshold > 0U) &&
                   (*ventTestSkipSpaces(arguments) == '\0')) {
            lTriggerType = VENT_TRIGGER_PRESSURE;
        } else if (ventTestTokenMatch(&arguments, "flow") &&
                   ventTestUnsignedParse(&arguments, &lTriggerThreshold) &&
                   (lTriggerThreshold > 0U) &&
                   (*ventTestSkipSpaces(arguments) == '\0')) {
            lTriggerType = VENT_TRIGGER_FLOW;
        } else {
            ventTestUsageShow();
            return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
        }

        lConfiguredMode = breathSchedulerModeGet();
        (void)breathSchedulerStop();
        if (lConfiguredMode == VENT_MD_VAC) {
            lVacSettings = GetVentVacSettings();
            lPreviousVacSettings = *lVacSettings;
            lVacSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lVacSettings->pressureTriggerCmh2o = -((float)lTriggerThreshold / 100.0F);
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lVacSettings->flowTriggerLpm = (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerTestModeSet((uint8_t)lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lVacSettings = lPreviousVacSettings;
                (void)breathSchedulerTestModeSet((uint8_t)lConfiguredMode);
            }
        } else if (lConfiguredMode == VENT_MD_CPAP_PSV) {
            lCpapPsvSettings = GetVentCpapPsvSettings();
            lPreviousCpapPsvSettings = *lCpapPsvSettings;
            lCpapPsvSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lCpapPsvSettings->pressureTriggerCmh2o =
                    -((float)lTriggerThreshold / 100.0F);
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lCpapPsvSettings->flowTriggerLpm =
                    (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerTestModeSet((uint8_t)lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lCpapPsvSettings = lPreviousCpapPsvSettings;
                (void)breathSchedulerTestModeSet((uint8_t)lConfiguredMode);
            }
        } else if (lConfiguredMode == VENT_MD_P_SIMV) {
            stVentPSimvSettings *lSettings = GetVentPSimvSettings();
            stVentPSimvSettings lPrevious = *lSettings;
            lSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lSettings->pressureTriggerCmh2o = -(float)lTriggerThreshold / 100.0F;
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lSettings->flowTriggerLpm = (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerSettingsUpdate(lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lSettings = lPrevious;
            }
        } else if (lConfiguredMode == VENT_MD_PRVC) {
            stVentPrvcSettings *lSettings = GetVentPrvcSettings();
            stVentPrvcSettings lPrevious = *lSettings;
            lSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lSettings->pressureTriggerCmh2o = -(float)lTriggerThreshold / 100.0F;
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lSettings->flowTriggerLpm = (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerSettingsUpdate(lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lSettings = lPrevious;
            }
        } else if (lConfiguredMode == VENT_MD_VS) {
            stVentVsSettings *lSettings = GetVentVsSettings();
            stVentVsSettings lPrevious = *lSettings;
            lSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lSettings->pressureTriggerCmh2o = -(float)lTriggerThreshold / 100.0F;
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lSettings->flowTriggerLpm = (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerSettingsUpdate(lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lSettings = lPrevious;
            }
        } else if (lConfiguredMode == VENT_MD_BAPAP) {
            stVentBapapSettings *lSettings = GetVentBapapSettings();
            stVentBapapSettings lPrevious = *lSettings;
            lSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lSettings->pressureTriggerCmh2o = -(float)lTriggerThreshold / 100.0F;
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lSettings->flowTriggerLpm = (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerSettingsUpdate(lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lSettings = lPrevious;
            }
        } else if (lConfiguredMode == VENT_MD_APRV) {
            stVentAprvSettings *lSettings = GetVentAprvSettings();
            stVentAprvSettings lPrevious = *lSettings;
            lSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lSettings->pressureTriggerCmh2o = -(float)lTriggerThreshold / 100.0F;
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lSettings->flowTriggerLpm = (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerSettingsUpdate(lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lSettings = lPrevious;
            }
        } else if (lConfiguredMode == VENT_MD_PRVC_SIMV) {
            stVentPrvcSimvSettings *lSettings = GetVentPrvcSimvSettings();
            stVentPrvcSimvSettings lPrevious = *lSettings;
            lSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lSettings->pressureTriggerCmh2o = -(float)lTriggerThreshold / 100.0F;
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lSettings->flowTriggerLpm = (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerSettingsUpdate(lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lSettings = lPrevious;
            }
        } else if (lConfiguredMode == VENT_MD_V_SIMV) {
            stVentVSimvSettings *lSettings = GetVentVSimvSettings();
            stVentVSimvSettings lPrevious = *lSettings;
            lSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lSettings->pressureTriggerCmh2o = -(float)lTriggerThreshold / 100.0F;
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lSettings->flowTriggerLpm = (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerSettingsUpdate(lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lSettings = lPrevious;
            }
        } else if (lConfiguredMode == VENT_MD_PSV_ST) {
            lPsvStSettings = GetVentPsvStSettings();
            lPreviousPsvStSettings = *lPsvStSettings;
            lPsvStSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lPsvStSettings->pressureTriggerCmh2o =
                    -((float)lTriggerThreshold / 100.0F);
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lPsvStSettings->flowTriggerLpm =
                    (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerTestModeSet((uint8_t)lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lPsvStSettings = lPreviousPsvStSettings;
                (void)breathSchedulerTestModeSet((uint8_t)lConfiguredMode);
            }
        } else {
            lConfiguredMode = VENT_MD_PAC;
            lPacSettings = GetVentPacSettings();
            lPreviousSettings = *lPacSettings;
            lPacSettings->triggerType = lTriggerType;
            if (lTriggerType == VENT_TRIGGER_PRESSURE) {
                lPacSettings->pressureTriggerCmh2o =
                    -((float)lTriggerThreshold / 100.0F);
            } else if (lTriggerType == VENT_TRIGGER_FLOW) {
                lPacSettings->flowTriggerLpm =
                    (float)lTriggerThreshold / 100.0F;
            }
            lStatus = breathSchedulerTestModeSet((uint8_t)lConfiguredMode);
            if (lStatus != BREATH_CONTROL_SUCCESS) {
                *lPacSettings = lPreviousSettings;
                (void)breathSchedulerTestModeSet((uint8_t)lConfiguredMode);
            }
        }
        LOG_I(gVentTestTag,
              "trigger mode=%u type=%u threshold100=%u status=%d",
              (unsigned int)lConfiguredMode,
              (unsigned int)lTriggerType,
              (unsigned int)lTriggerThreshold,
              (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "mode") &&
               ventTestUnsignedParse(&arguments, &lMode) &&
               (lMode <= UINT8_MAX) &&
               (*ventTestSkipSpaces(arguments) == '\0')) {
        lStatus = breathSchedulerTestModeSet((uint8_t)lMode);
        LOG_I(gVentTestTag, "mode %u status=%d", (unsigned int)lMode, (int)lStatus);
    } else if (ventTestTokenMatch(&arguments, "run")) {
        arguments = ventTestSkipSpaces(arguments);
        if (((arguments[0] != '0') && (arguments[0] != '1')) ||
            (*ventTestSkipSpaces(arguments + 1) != '\0')) {
            ventTestUsageShow();
            return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
        }
        lRun = (uint8_t)(arguments[0] - '0');
        lStatus = breathSchedulerTestRunSet(lRun);
        LOG_I(gVentTestTag, "run %u status=%d", (unsigned int)lRun, (int)lStatus);
    } else {
        ventTestUsageShow();
        return CONSOLE_COMMAND_RESULT_INVALID_ARGUMENT;
    }

    return (lStatus == BREATH_CONTROL_SUCCESS) ? CONSOLE_COMMAND_RESULT_OK : CONSOLE_COMMAND_RESULT_ERROR;
}

static const stConsoleCommand gVentTestConsoleCommand = {
    "vt",
    "Ventilation test: select mode or running state",
    ventTestConsoleCommand
};

bool ventTestConsoleRegister(void)
{
    return consoleRegisterCommand(&gVentTestConsoleCommand);
}
/**************************End of file********************************/

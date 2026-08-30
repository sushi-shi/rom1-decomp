#include <rva.h>

#include <Scenario/ScenarioConfig.h>

#include <Bute/ButeMgr.h>

RVA(0x000878a0, 0xa1)
i32 __stdcall GetMissionObjectCount(i32 mission) {
    CButeMgr config(DATA_COMPGEN(0x001bcc68, "Scenario\\GlobalMap.reg"));
    CString missionTag;
    missionTag.Format(DATA_COMPGEN(0x001bf0d0, "Mission%d"), mission, 0);
    return config.GetInt(
        DATA_COMPGEN(0x001bf0c0, "MissionObjects"), static_cast<const char*>(missionTag), 1
        )
        - 1;
}

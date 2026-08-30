#include <rva.h>

#include <Bute/ButeMgr.h>

// Located from the exact call/cleanup edges in GetMissionObjectCount. These
// bodies remain the next Bute reconstruction slice; their claims provision
// the real C++ identities for callers today.
RVA(0x000cb140, 0x1d2)
CButeMgr::CButeMgr(const char* filename) {
    (void)filename;
}

RVA(0x000cbf20, 0x25)
CButeMgr::~CButeMgr() {}

RVA(0x000ccc00, 0x90)
i32 CButeMgr::GetInt(const char* tag, const char* key, i32 defaultValue) {
    (void)tag;
    (void)key;
    return defaultValue;
}

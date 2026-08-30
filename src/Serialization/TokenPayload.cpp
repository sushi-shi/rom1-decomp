#include <rva.h>

#include <Serialization/SpellObjects.h>

RVA(0x00141830, 0x28f)
CWorldMapData::CWorldMapData(CScenarioResource* resource, CWorldItemManager* itemManager) {
    (void)resource;
    (void)itemManager;
}

RVA(0x00144a70, 0x23)
void CTokenPayload::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

RVA(0x00144aa0, 0x298)
void CWorldMapData::Serialize(CArchive& archive) {
    (void)archive;
}

RVA(0x0014d530, 0x14d)
void CWorldMapData::Activate() {}

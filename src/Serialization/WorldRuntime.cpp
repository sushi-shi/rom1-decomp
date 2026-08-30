#include <rva.h>

#include <Serialization/ReferenceWorld.h>
#include <Serialization/WorldRuntimeRecords.h>

RVA(0x0012c440, 0x199)
CWorldRuntime::CWorldRuntime(CWorldMapData* mapData, CWorldObjectRegistry* registry) {
    (void)mapData;
    (void)registry;
}

RVA(0x00139310, 0x40)
void CPlayerArchiveBlock::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

RVA(0x00139350, 0x1ce)
void CWorldRuntime::Serialize(CArchive& archive) {
    (void)archive;
}

RVA(0x0013b8b0, 0x7)
void CWorldRuntime::Activate() {}

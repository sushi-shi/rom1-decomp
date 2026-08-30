#include <rva.h>

#include <Serialization/SpellObjects.h>
#include <Serialization/WorldRuntimeRecords.h>

RVA_COMPGEN(0x00124bc0, 0x40, ?SerializeElements@@YGXAAVCArchive@@PAKH@Z)

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
    CList<DWORD, DWORD> exceptionalTiles;

    if (archive.IsStoring()) {
        const BYTE* highTileCodes = m_highTileCodes;
        const BYTE* highTileCode = &highTileCodes[0x807];
        for (UINT remaining = 0xe5e7; remaining != 0; remaining--, highTileCode++) {
            if (*highTileCode > 15) {
                DWORD value = highTileCode - highTileCodes;
                value <<= 8;
                value += *highTileCode;
                value <<= 8;
                value += highTileCode[-0x10000];
                exceptionalTiles.AddTail(value);
            }
        }

        exceptionalTiles.Serialize(archive);
        m_records.Serialize(archive);
        archive << reinterpret_cast<LONG>(this); // proven raw pointer identity
    }

    if (archive.IsLoading()) {
        exceptionalTiles.Serialize(archive);
        m_records.Serialize(archive);

        LONG reference;
        archive >> reference;
        void* referenceKey = reinterpret_cast<void*>(reference); // proven raw pointer identity
        g_referenceWorld->m_references[referenceKey] = this;

        POSITION position = exceptionalTiles.GetHeadPosition();
        while (position != NULL) {
            DWORD value = exceptionalTiles.GetNext(position);
            WORD index = HIWORD(value);
            m_highTileCodes[index] = HIBYTE(LOWORD(value));
            m_lowTileCodes[index] = LOBYTE(value);
        }
    }
}

RVA(0x0014d500, 0x26)
void CUnitRawArchiveRecord::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

RVA(0x0014d530, 0x14d)
void CWorldMapData::Activate() {}

RVA_COMPGEN(0x0014fa40, 0x20e, ?Serialize@?$CMap@GGUCUnitMapValue@@U1@@@UAEXAAVCArchive@@@Z)
template void CUnitValueMap::Serialize(CArchive& archive);

RVA_COMPGEN(0x0014ff20, 0x84, ??1?$CMap@GGUCWorldMapRecord@@AAU1@@@UAE@XZ)
RVA_COMPGEN(0x0014ffb0, 0x1a8, ?Serialize@?$CMap@GGUCWorldMapRecord@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x001501d0, 0x118, ?Serialize@?$CList@UCUnitListValue@@U1@@@UAEXAAVCArchive@@@Z)
template void CUnitValueList::Serialize(CArchive& archive);

RVA_COMPGEN(0x001502f0, 0x7d, ?AddTail@?$CList@KK@@QAEPAU__POSITION@@K@Z)
RVA_COMPGEN(0x00150370, 0x65, ??1?$CList@KK@@UAE@XZ)
RVA_COMPGEN(0x001503e0, 0x118, ?Serialize@?$CList@KK@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00150520, 0x1e, ??_G?$CMap@GGUCWorldMapRecord@@AAU1@@@UAEPAXI@Z)
RVA_COMPGEN(0x00150560, 0x1e, ??_G?$CList@KK@@UAEPAXI@Z)
RVA_COMPGEN(0x00150780, 0x5e, ?NewNode@?$CList@KK@@IAEPAUCNode@1@PAU21@0@Z)

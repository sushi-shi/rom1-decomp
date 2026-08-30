#include <rva.h>

#include <Serialization/ReferenceWorld.h>
#include <Serialization/SpellObjects.h>

RVA(0x0011f010, 0x10)
CWorldObjectIterator::CWorldObjectIterator() {}

RVA(0x0011f020, 0x50)
CWorldObject* CWorldObjectIterator::First(CWorldObjectRegistry* registry) {
    (void)registry;
    return 0;
}

RVA(0x0011f070, 0x30)
CWorldObject* CWorldObjectIterator::Next() {
    return 0;
}

RVA(0x0011f0a0, 0xe)
CPlayerUnitGroupIterator::CPlayerUnitGroupIterator() {}

RVA(0x0011f0b0, 0x43)
CWorldItemList* CPlayerUnitGroupIterator::First(CPlayerUnitGroupCollection* groups) {
    m_groups = groups;
    m_position = m_groups->m_groups.GetHeadPosition();
    if (m_position != 0) {
        return m_groups->m_groups.GetNext(m_position);
    }
    return 0;
}

RVA(0x0011f100, 0x29)
CWorldItemList* CPlayerUnitGroupIterator::Next() {
    if (m_position != 0) {
        return m_groups->m_groups.GetNext(m_position);
    }
    return 0;
}

// The iterator's const collection view naturally selects the two by-value
// CList accessors emitted in retail's template band.
RVA_COMPGEN(0x00124320, 0x11, ?GetHeadPosition@?$CList@PAVCPlayerUnitGroup@@PAV1@@@QBEPAU__POSITION@@XZ)
RVA_COMPGEN(0x00124340, 0x27, ?GetNext@?$CList@PAVCPlayerUnitGroup@@PAV1@@@QBEPAVCPlayerUnitGroup@@AAPAU__POSITION@@@Z)

#include <rva.h>

#include <Serialization/ArchiveArrays.h>
#include <Serialization/SpellObjects.h>
#include <Serialization/WorldRuntimeRecords.h>

// The 48-byte CArray element stride and the naturally selected operator[]
// specialization identify the table used to rebuild Unit+0x3c after load.
// clang-format off
DATA(0x00209afc) extern CPrimaryStateRecordArray g_unitStates;
// clang-format on

RVA(0x000d9f67, 0x3f)
static void MarkTokenIdSeen(WORD value) {
    g_seenTokenIds[value >> 5] |= 1 << (value & 31);
}

// Located support identities. Their bodies remain explicit campaign work;
// CReferenceWorld::Serialize fixes their receivers, signatures, and calls.
RVA(0x0010fc4d, 0x1c)
void CWorldItemManager::Remove(CWorldItem* item) {
    (void)item;
}

RVA(0x0011005d, 0x16)
CScenarioPrimary::CScenarioPrimary() {}

RVA(0x00110216, 0x22)
CScenarioSecondary::CScenarioSecondary() {}

RVA(0x0011033a, 0x19)
void CScenarioPrimary::Serialize(CArchive& archive) {
    (void)archive;
}

// Source-complete: normalized bytes are identical; the sole remaining score
// residue is CObject::operator new versus retail's unclaimed 0x231d0 referent.
RVA(0x00110577, 0x8a8)
void Unit::Serialize(CArchive& archive) {
    Token::Serialize(archive);
    m_effects.Serialize(archive);
    m_words15c.Serialize(archive);
    m_words178.Serialize(archive);
    m_damagea6.Serialize(archive);
    m_sharedbe.Serialize(archive);
    m_damage114.Serialize(archive);
    m_blockd4.Serialize(archive);
    m_raw154->Serialize(archive);
    m_words158->Serialize(archive);

    if (archive.IsStoring()) {
        archive << m_values49[0];
        archive << m_values49[1];
        archive << m_values49[2];
        archive << m_values49[3];
        archive.Write(m_raw50, sizeof(m_raw50));
        archive.Write(m_raw54, sizeof(m_raw54));
        archive.Write(m_raw58, sizeof(m_raw58));
        archive << m_value60;
        archive << m_value61;
        archive << m_value6c;
        archive << m_item74;
        archive << m_item78;
        archive << m_value80;
        archive << m_value84;
        archive << m_value86;
        archive << m_value88;
        archive << m_value8a;
        archive << m_value8c;
        archive << m_value8e;
        archive << m_value90;
        archive << m_value92;
        archive << m_value94;
        archive << m_value96;
        archive << m_value98;
        archive << m_value9a;
        archive << m_value9c;
        archive << m_value9e;
        archive << m_valuea2;
        archive << m_valuea3;
        archive << m_valuea0;
        archive << m_valuea4;
        archive << m_value12c;
        archive << m_value130;
        archive << m_value134;
        archive << m_value135;
        archive << m_value136;
        archive << m_value138;
        archive << m_value13c;
        m_value148 = m_value14c;
        archive << m_value148;
        archive << m_value144;
        archive << m_item68;
        if (m_itemList7c != 0) {
            archive << static_cast<BYTE>(1);
            m_itemList7c->Serialize(archive);
        } else {
            archive << static_cast<BYTE>(0);
        }
        if (m_spellbook140 != 0) {
            archive << static_cast<BYTE>(1);
            m_spellbook140->Serialize(archive);
        } else {
            archive << static_cast<BYTE>(0);
        }
        archive << m_reference5c;
        archive << m_reference64;
        archive << m_reference44;
        archive << m_reference40;
        archive << m_value48;
    } else {
        archive >> m_values49[0];
        archive >> m_values49[1];
        archive >> m_values49[2];
        archive >> m_values49[3];
        archive.Read(m_raw50, sizeof(m_raw50));
        archive.Read(m_raw54, sizeof(m_raw54));
        archive.Read(m_raw58, sizeof(m_raw58));
        archive >> m_value60;
        archive >> m_value61;
        archive >> m_value6c;
        archive >> m_item74;
        archive >> m_item78;
        archive >> m_value80;
        archive >> m_value84;
        archive >> m_value86;
        archive >> m_value88;
        archive >> m_value8a;
        archive >> m_value8c;
        archive >> m_value8e;
        archive >> m_value90;
        archive >> m_value92;
        archive >> m_value94;
        archive >> m_value96;
        archive >> m_value98;
        archive >> m_value9a;
        archive >> m_value9c;
        archive >> m_value9e;
        archive >> m_valuea2;
        archive >> m_valuea3;
        archive >> m_valuea0;
        archive >> m_valuea4;
        archive >> m_value12c;
        archive >> m_value130;
        archive >> m_value134;
        archive >> m_value135;
        archive >> m_value136;
        archive >> m_value138;
        archive >> m_value13c;
        archive >> m_value148;
        archive >> m_value144;
        archive >> m_item68;

        BYTE present;
        archive >> present;
        if (present != 0) {
            m_itemList7c->Serialize(archive);
        }
        archive >> present;
        if (present != 0) {
            m_spellbook140 = new Spellbook;
            m_spellbook140->Serialize(archive);
        }

        UINT reference;
        archive >> reference;
        m_reference5c = reference;
        archive >> reference;
        m_reference64 = reference;
        archive >> reference;
        m_reference44 = reference;
        archive >> reference;
        m_reference40 = reference;
        archive >> m_value48;

        m_value14c = static_cast<BYTE>(m_value148);
        if (!TokenVirtual12()) {
            m_state3c = &g_unitStates[m_value0c];
            m_value14c = 0;
        } else {
            m_state3c = 0;
        }
    }
}

RVA(0x00110ebb, 0x16e)
void Token::Serialize(CArchive& archive) {
    CObject::Serialize(archive);
    m_payload->Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value04;
        archive << m_value0c;
        archive << m_value0e;
        archive << m_value08;
        archive << m_value18;
        archive << m_value1c;
        archive << reinterpret_cast<UINT>(this); // proven raw pointer identity
        archive << m_reference14;
    } else {
        archive >> m_value04;
        if (m_value04 != 0) {
            MarkTokenIdSeen(static_cast<WORD>(m_value04));
        }
        archive >> m_value0c;
        archive >> m_value0e;
        archive >> m_value08;
        archive >> m_value18;
        archive >> m_value1c;
        UINT value;
        archive >> value;
        g_referenceWorld->m_references.SetAt(
            reinterpret_cast<void*>(value), // proven raw pointer identity
            this
        );
        archive >> value;
        m_reference14 = value;
        ResolveTokenReference(&m_reference14);
    }
}

RVA(0x0011108e, 0x5a)
void CWorldObjectRegistry::Serialize(CArchive& archive) {
    (void)archive;
}

RVA(0x001114fc, 0x19)
void CScenarioTertiary::Serialize(CArchive& archive) {
    (void)archive;
}

RVA(0x00111515, 0x1c)
void CScenarioSecondary::Serialize(CArchive& archive) {
    (void)archive;
}

RVA(0x00111531, 0x5a)
void CScenarioSecondary::Activate() {}

RVA(0x001117bf, 0xd9)
void Humanoid::Serialize(CArchive& archive) {
    Unit::Serialize(archive);
    if (archive.IsStoring()) {
        archive.Write(m_values1cc, sizeof(m_values1cc));
        for (int i = 1; i < 13; i++) {
            archive << m_items198[i];
        }
        archive << m_diary1e4;
    } else {
        archive.Read(m_values1cc, sizeof(m_values1cc));
        for (int i = 1; i < 13; i++) {
            archive >> m_items198[i];
        }
        archive >> m_diary1e4;
    }
}

RVA(0x00111ab2, 0x63)
void CUnitItemList::Serialize(CArchive& archive) {
    m_items.Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value1c;
        archive << m_value20;
    } else {
        archive >> m_value1c;
        archive >> m_value20;
    }
}

RVA(0x00111ba2, 0x67)
void VirtualCaster::Serialize(CArchive& archive) {
    Token::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value3c;
        archive.Write(m_values40, 6);
    } else {
        archive >> m_value3c;
        archive.Read(m_values40, 6);
    }
}

RVA(0x001123c8, 0x157f)
CScenarioResource::CScenarioResource(const char* path) {
    (void)path;
}

RVA(0x0011396f, 0x3bb)
CScenarioResource::~CScenarioResource() {}

RVA(0x00114570, 0x20)
CScenarioTertiary::CScenarioTertiary() {}

RVA(0x001149c0, 0x60)
Spellbook::Spellbook() {}

RVA_COMPGEN(0x001176a0, 0x1c, ?SetAt@CMapPtrToPtr@@QAEXPAX0@Z)
RVA_COMPGEN(0x00118040, 0x20, ??6CArchive@@QAEAAV0@D@Z)
RVA_COMPGEN(0x00118060, 0x20, ??5CArchive@@QAEAAV0@AAD@Z)

// Their paired retail placement with the matching CList<TYPE, TYPE>
// specializations proves these two game-owned template instantiations.
RVA_COMPGEN(0x00118520, 0xb0, ?Serialize@?$CArchivePointerList@PAVEffect@@@@QAEXAAVCArchive@@@Z)
template void CArchivePointerList<Effect*>::Serialize(CArchive& archive);

RVA_COMPGEN(0x00118990, 0xb0, ?Serialize@?$CArchivePointerList@PAVItem@@@@QAEXAAVCArchive@@@Z)
template void CArchivePointerList<Item*>::Serialize(CArchive& archive);

RVA_COMPGEN(0x00119d10, 0x20, ??A?$CArray@UCPrimaryStateRecord@@AAU1@@@QAEAAUCPrimaryStateRecord@@H@Z)

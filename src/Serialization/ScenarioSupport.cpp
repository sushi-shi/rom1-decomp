#include <rva.h>

#include <Serialization/ArchiveArrays.h>
#include <Serialization/SpellObjects.h>
#include <Serialization/WorldRuntimeRecords.h>

#include <string.h>

// The 48-byte CArray element stride and the naturally selected operator[]
// specialization identify the table used to rebuild Unit+0x3c after load.
// clang-format off
DATA(0x00209afc) extern CPrimaryStateRecordArray g_unitStates;
// clang-format on

// The shared template operators establish the three 60-byte equipment tables,
// the 64-byte base-item table, and Human's distinct 48-byte state table.
// clang-format off
DATA(0x00209a98) extern CEquipmentDefinitionArray g_shieldDefinitions;
DATA(0x00209aac) extern CEquipmentDefinitionArray g_armorDefinitions;
DATA(0x00209ac0) extern CEquipmentDefinitionArray g_weaponDefinitions;
DATA(0x00209ad4) extern CItemDefinitionArray g_itemDefinitions;
DATA(0x00209b10) extern CSecondaryStateRecordArray g_humanStates;

// CStringArray::Serialize is the pinned MFC provider.  These are game-owned
// tables passed to it by the Data.bin serializer; their category identities
// are fixed by the adjacent .csv bootstrap paths.
DATA(0x001f21b0) extern CStringArray g_materialShapeNames;
DATA(0x00209978) extern CStringArray g_magicNames;
DATA(0x00209488) extern CStringArray g_equipmentNames;
DATA(0x00203b68) extern CStringArray g_magicItemNames;
DATA(0x0020a730) extern CStringArray g_unitNames;
DATA(0x001f2148) extern CStringArray g_humanNames;
DATA(0x001f2198) extern CStringArray g_buildingNames;
DATA(0x001f2160) extern CStringArray g_spellNames;
// clang-format on

RVA(0x000d9f67, 0x3f)
static void MarkTokenIdSeen(WORD value) {
    g_seenTokenIds[value >> 5] |= 1 << (value & 31);
}

// Source-complete Data.bin serializer.  Every element loop dispatches the
// canonical TableLine subtype's proven virtual Serialize slot.
RVA(0x000dbd14, 0x943)
void CStaticDataTables::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        int i;
        g_materialShapeNames.Serialize(archive);

        archive << static_cast<UINT>(m_shapes.GetSize());
        for (i = 0; i < m_shapes.GetSize(); i++) {
            m_shapes[i].Serialize(archive);
        }

        archive << static_cast<UINT>(m_materials.GetSize());
        for (i = 0; i < m_materials.GetSize(); i++) {
            m_materials[i].Serialize(archive);
        }

        g_magicNames.Serialize(archive);
        archive << static_cast<UINT>(m_magic.GetSize());
        for (i = 0; i < m_magic.GetSize(); i++) {
            m_magic[i].Serialize(archive);
        }

        g_equipmentNames.Serialize(archive);
        archive << static_cast<UINT>(m_armors.GetSize());
        for (i = 1; i < m_armors.GetSize(); i++) {
            m_armors[i].Serialize(archive);
        }

        archive << static_cast<UINT>(m_shields.GetSize());
        for (i = 1; i < m_shields.GetSize(); i++) {
            m_shields[i].Serialize(archive);
        }

        archive << static_cast<UINT>(m_weapons.GetSize());
        for (i = 1; i < m_weapons.GetSize(); i++) {
            m_weapons[i].Serialize(archive);
        }

        g_magicItemNames.Serialize(archive);
        archive << static_cast<UINT>(m_magicItems.GetSize());
        for (i = 1; i < m_magicItems.GetSize(); i++) {
            m_magicItems[i].Serialize(archive);
        }

        g_unitNames.Serialize(archive);
        archive << static_cast<UINT>(m_units.GetSize());
        for (i = 1; i < m_units.GetSize(); i++) {
            m_units[i].Serialize(archive);
        }

        g_humanNames.Serialize(archive);
        archive << static_cast<UINT>(m_humans.GetSize());
        for (i = 1; i < m_humans.GetSize(); i++) {
            m_humans[i].Serialize(archive);
        }

        g_buildingNames.Serialize(archive);
        archive << static_cast<UINT>(m_buildings.GetSize());
        for (i = 1; i < m_buildings.GetSize(); i++) {
            m_buildings[i].Serialize(archive);
        }

        g_spellNames.Serialize(archive);
        archive << static_cast<UINT>(m_spells.GetSize());
        for (i = 1; i < m_spells.GetSize(); i++) {
            m_spells[i].Serialize(archive);
        }
        return;
    }

    int i;
    UINT count;
    g_materialShapeNames.Serialize(archive);

    archive >> count;
    m_shapes.SetSize(count);
    for (i = 0; i < m_shapes.GetSize(); i++) {
        m_shapes[i].Serialize(archive);
    }

    archive >> count;
    m_materials.SetSize(count);
    for (i = 0; i < m_materials.GetSize(); i++) {
        m_materials[i].Serialize(archive);
    }

    g_magicNames.Serialize(archive);
    archive >> count;
    m_magic.SetSize(count);
    for (i = 0; i < m_magic.GetSize(); i++) {
        m_magic[i].Serialize(archive);
    }

    g_equipmentNames.Serialize(archive);
    archive >> count;
    m_armors.SetSize(count);
    for (i = 1; i < m_armors.GetSize(); i++) {
        m_armors[i].Serialize(archive);
    }

    archive >> count;
    m_shields.SetSize(count);
    for (i = 1; i < m_shields.GetSize(); i++) {
        m_shields[i].Serialize(archive);
    }

    archive >> count;
    m_weapons.SetSize(count);
    for (i = 1; i < m_weapons.GetSize(); i++) {
        m_weapons[i].Serialize(archive);
    }

    g_magicItemNames.Serialize(archive);
    archive >> count;
    m_magicItems.SetSize(count);
    for (i = 1; i < m_magicItems.GetSize(); i++) {
        m_magicItems[i].Serialize(archive);
    }

    g_unitNames.Serialize(archive);
    archive >> count;
    m_units.SetSize(count);
    for (i = 1; i < m_units.GetSize(); i++) {
        m_units[i].Serialize(archive);
    }

    g_humanNames.Serialize(archive);
    archive >> count;
    m_humans.SetSize(count);
    for (i = 1; i < m_humans.GetSize(); i++) {
        m_humans[i].Serialize(archive);
    }

    g_buildingNames.Serialize(archive);
    archive >> count;
    m_buildings.SetSize(count);
    for (i = 1; i < m_buildings.GetSize(); i++) {
        m_buildings[i].Serialize(archive);
    }

    g_spellNames.Serialize(archive);
    archive >> count;
    m_spells.SetSize(count);
    for (i = 1; i < m_spells.GetSize(); i++) {
        m_spells[i].Serialize(archive);
    }
}

// The compact record constructor clears its recovered 0x50-byte state,
// restores the one default flag, and owns a separately allocated WORD list.
CWordListRecordCompact::CWordListRecordCompact() {
    memset(this, 0, sizeof(*this));
    m_record[8] = 0;
    m_record[9] = 0;
    m_record[0x20] = 0;
    m_record[0x45] = 1;
    m_words = new CList<WORD, WORD>;
}

CPlayerUnitGroup::CPlayerUnitGroup() : m_values20(10), m_reference40(0), m_reference44(0) {
    m_archive3c = new CWordListRecordCompact;
}

void CPlayerUnitGroup::AddUnit(Unit* unit) {
    if (unit->m_group70 != 0) {
        unit->m_group70->RemoveUnit(unit);
    }
    m_units.AddTail(unit);
    unit->m_group70 = this;
    m_reference44 = unit->m_reference14;
}

void CPlayerUnitGroup::RemoveUnit(Unit* unit) {
    POSITION position = m_units.Find(unit);
    if (position != 0) {
        m_units.RemoveAt(position);
    }
    unit->m_group70 = 0;
}

int CPlayerUnitGroupCollection::GetCount() const {
    return m_groups.GetCount();
}

void CPlayerUnitGroupCollection::Add(CPlayerUnitGroup* group) {
    m_groups.AddTail(group);
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

RVA(0x00110353, 0x10d)
void CPlayerUnitGroupCollection::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive << static_cast<UINT>(GetCount());
        CPlayerUnitGroupIterator iterator;
        CPlayerUnitGroup* group = static_cast<CPlayerUnitGroup*>(iterator.First(this));
        while (group != 0) {
            group->Serialize(archive);
            group = static_cast<CPlayerUnitGroup*>(iterator.Next());
        }
        return;
    }

    UINT count;
    archive >> count;
    for (int i = 1; i <= static_cast<int>(count); i++) {
        CPlayerUnitGroup* group = new CPlayerUnitGroup;
        group->Serialize(archive);
        Add(group);
    }
}

RVA(0x001104d6, 0xa1)
void Weapon::Serialize(CArchive& archive) {
    Item::Serialize(archive);
    m_damage52.Serialize(archive);
    m_shared6a.Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value50;
        archive << m_spell80;
    } else {
        archive >> m_value50;
        archive >> m_spell80;
        m_definition3c = &g_weaponDefinitions[m_value0c];
    }
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

RVA(0x0011103f, 0x4f)
void Shield::Serialize(CArchive& archive) {
    Item::Serialize(archive);
    m_shared50.Serialize(archive);
    if (archive.IsStoring()) {
        return;
    }
    m_definition3c = &g_shieldDefinitions[m_value0c];
}

RVA(0x0011108e, 0x5a)
void CWorldObjectRegistry::Serialize(CArchive& archive) {
    (void)archive;
}

RVA(0x001110e8, 0x39e)
void Player::Serialize(CArchive& archive) {
    CObject::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_name18;
        archive << m_value04;
        archive << m_value08;
        archive.Write(m_raw10, sizeof(m_raw10));
        archive << m_value44;
        archive << m_value28;
        archive << m_value2c;
        archive << TransformPlayerReference(m_reference38);
        archive << m_value3c;
        archive << m_value3d;
        archive << TransformPlayerReference(m_reference48);
        archive << m_value50;

        short value54 = static_cast<short>(m_value54 > 0x7fff ? 0x7fff : m_value54);
        short value4c = static_cast<short>(m_value4c > 0x7fff ? 0x7fff : m_value4c);
        archive << value54;
        archive << value4c;
        archive << m_value58;
        archive << m_reference34;
        archive << reinterpret_cast<UINT>(this); // proven raw pointer identity
    } else {
        archive >> m_name18;
        archive >> m_value04;
        archive >> m_value08;
        archive.Read(m_raw10, sizeof(m_raw10));
        archive >> m_value44;
        archive >> m_value28;
        archive >> m_value2c;
        archive >> m_reference38;
        m_reference38 = TransformPlayerReference(m_reference38);
        archive >> m_value3c;
        archive >> m_value3d;
        archive >> m_reference48;
        m_reference48 = TransformPlayerReference(m_reference48);
        archive >> m_value50;

        short value54;
        short value4c;
        archive >> value54;
        archive >> value4c;
        m_value54 = value54;
        m_value4c = value4c;
        archive >> m_value58;

        UINT reference;
        archive >> reference;
        m_reference34 = reference;
        archive >> reference;
        g_referenceWorld->m_references.SetAt(
            reinterpret_cast<void*>(reference), // proven raw pointer identity
            this
        );
    }

    m_groups24->Serialize(archive);
    m_archive30->Serialize(archive);
    m_object40->Serialize(archive);

    if (!archive.IsStoring()) {
        ResolvePlayerReference(&m_reference34);

        CPlayerUnitGroupIterator groups;
        CWorldItemList* group = groups.First(m_groups24);
        while (group != 0) {
            CWorldItemIterator items;
            CWorldItem* item = items.First(group);
            while (item != 0) {
                m_itemManager20->Remove(item);
                item->m_owner14 = this;
                item = items.Next();
            }
            group = groups.Next();
        }
    }
}

RVA(0x00111486, 0x76)
void Diary::Serialize(CArchive& archive) {
    m_entries04.Serialize(archive);
    m_entries18.Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_reference2c;
    } else {
        UINT reference;
        archive >> reference;
        m_reference2c = reference;
        ResolveTokenReference(&m_reference2c);
    }
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

RVA(0x0011158b, 0xc8)
void Outpost::Serialize(CArchive& archive) {
    Building::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value84;
        archive << m_value88;
        archive << m_value80;
        archive << m_value8c;
    } else {
        archive >> m_value84;
        archive >> m_value88;
        archive >> m_value80;
        archive >> m_value8c;
    }
    m_placements.Serialize(archive);
}

RVA(0x00111653, 0x16c)
void Item::Serialize(CArchive& archive) {
    Token::Serialize(archive);
    m_effects.Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value40;
        archive << m_value42;
        archive << m_value44;
        archive << m_value45;
        archive << m_value46;
        archive << m_value48;
        archive << m_value4a;
        archive << m_value47;
    } else {
        archive >> m_value40;
        archive >> m_value42;
        archive >> m_value44;
        archive >> m_value45;
        archive >> m_value46;
        archive >> m_value48;
        archive >> m_value4a;
        archive >> m_value47;
        if (g_itemDefinitions.GetSize() > m_value0c) {
            m_definition3c = &g_itemDefinitions[m_value0c];
        } else {
            m_definition3c = 0;
        }
    }
}

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

RVA(0x00111898, 0xab)
void Human::Serialize(CArchive& archive) {
    Humanoid::Serialize(archive);
    if (archive.IsStoring()) {
        return;
    }
    if (m_value0e < 0x21) {
        m_state3c = &g_humanStates[m_value0c];
    } else {
        m_state3c = &g_humanStates[5];
    }

    if (m_value14c != 0) {
        if (m_state3c != 0) {
            if (m_state3c->m_name.Find("NPC") == -1) {
                m_value14c = 0;
            }
        } else {
            m_value14c = 0;
        }
    }
}

RVA(0x00111943, 0x54)
void Sack::Serialize(CArchive& archive) {
    Token::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value3c;
    } else {
        archive >> m_value3c;
    }
    m_itemList40->Serialize(archive);
}

void CPlayerUnitGroup::Serialize(CArchive& archive) {
    m_values20.Serialize(archive);
    m_archive3c->Serialize(archive);
    if (archive.IsStoring()) {
        m_units.Serialize(archive);
        archive << m_reference1c;
        archive << m_reference40;
        archive << m_reference44;
        return;
    }

    m_units.RemoveAll();
    UINT count;
    archive >> count;
    for (int i = 1; i <= static_cast<int>(count); i++) {
        Unit* unit;
        archive >> unit;
        AddUnit(unit);
    }
    archive >> m_reference1c;

    UINT reference;
    archive >> reference;
    m_reference40 = reference;
    ResolvePlayerReference(&m_reference40);
    archive >> reference;
    m_reference44 = reference;
    ResolveTokenReference(&m_reference44);
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

RVA(0x00111b35, 0x6d)
void Armor::Serialize(CArchive& archive) {
    Item::Serialize(archive);
    m_shared52.Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value50;
    } else {
        archive >> m_value50;
        m_definition3c = &g_armorDefinitions[m_value0c];
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

RVA_COMPGEN(0x00118c10, 0x20, ?GetSize@?$CArray@VCTableLineRawBlock@@AAV1@@@QBEHXZ)
RVA_COMPGEN(0x00118e50, 0x20, ??A?$CArray@VCTableLineRawBlock@@AAV1@@@QAEAAVCTableLineRawBlock@@H@Z)
RVA_COMPGEN(0x00118fb0, 0x20, ?GetSize@?$CArray@VCTableLineWordBlock@@AAV1@@@QBEHXZ)
RVA_COMPGEN(0x00119210, 0x20, ??A?$CArray@VCTableLineWordBlock@@AAV1@@@QAEAAVCTableLineWordBlock@@H@Z)
RVA_COMPGEN(0x00119370, 0x20, ?GetSize@?$CArray@VCTableLineWordBlockLabel@@AAV1@@@QBEHXZ)
RVA_COMPGEN(0x001195b0, 0x20, ??A?$CArray@VCTableLineWordBlockLabel@@AAV1@@@QAEAAVCTableLineWordBlockLabel@@H@Z)
RVA_COMPGEN(0x00119710, 0x20, ?GetSize@?$CArray@VTableLine@@AAV1@@@QBEHXZ)
RVA_COMPGEN(0x00119970, 0x20, ??A?$CArray@VTableLine@@AAV1@@@QAEAAVTableLine@@H@Z)
RVA_COMPGEN(0x00119ad0, 0x20, ?GetSize@?$CArray@VCTableLineStringPair@@AAV1@@@QBEHXZ)
RVA_COMPGEN(0x00119d10, 0x20, ??A?$CArray@VCTableLineStringPair@@AAV1@@@QAEAAVCTableLineStringPair@@H@Z)
RVA_COMPGEN(0x00119e70, 0x20, ?GetSize@?$CArray@VCTableLineStringDecade@@AAV1@@@QBEHXZ)
RVA_COMPGEN(0x0011a0d0, 0x20, ??A?$CArray@VCTableLineStringDecade@@AAV1@@@QAEAAVCTableLineStringDecade@@H@Z)
RVA_COMPGEN(0x0011a230, 0x20, ?GetSize@?$CArray@VCTableLineBaseOnly@@AAV1@@@QBEHXZ)
RVA_COMPGEN(0x0011a5f0, 0x20, ?GetSize@?$CArray@VCTableLineLabel@@AAV1@@@QBEHXZ)

RVA_COMPGEN(0x00122960, 0x20, ?ElementAt@?$CArray@VCTableLineWordBlock@@AAV1@@@QAEAAVCTableLineWordBlock@@H@Z)
RVA_COMPGEN(0x00122b70, 0x20, ?ElementAt@?$CArray@VCTableLineWordBlockLabel@@AAV1@@@QAEAAVCTableLineWordBlockLabel@@H@Z)
RVA_COMPGEN(0x00123150, 0x20, ?ElementAt@?$CArray@VCTableLineStringDecade@@AAV1@@@QAEAAVCTableLineStringDecade@@H@Z)

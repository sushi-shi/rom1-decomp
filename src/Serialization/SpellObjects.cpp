#include <rva.h>

#include <Serialization/SpellObjects.h>

#include <Serialization/ArchiveArrays.h>

DATA(0x001cd6b0)
CReferenceWorld* g_referenceWorld;

DATA(0x0022c738)
UINT g_seenTokenIds[0x800];

// Keep the extern declaration on the DATA site so source-label extraction can
// bind the retail global without defining duplicate CArray storage in this TU.
// clang-format off
DATA(0x00209b4c) extern CSpellDefinitionArray g_spellDefinitions;
// clang-format on

typedef CArray<CTertiaryStateRecord, CTertiaryStateRecord&> CBuildingDefinitionArray;

// The 28-byte CArray element stride and the shared template bodies prove this
// definition-record identity; no original source name survives.
// clang-format off
DATA(0x00209b38) extern CBuildingDefinitionArray g_buildingDefinitions;
// clang-format on

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x000f2461, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Token*& value) {
    value = static_cast<Token*>(archive.ReadObject(&Token::classToken));
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x000f2a24, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, VirtualCaster*& value) {
    value = static_cast<VirtualCaster*>(archive.ReadObject(&VirtualCaster::classVirtualCaster));
    return archive;
}

RVA(0x000f2bf7, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Unit*& value) {
    value = static_cast<Unit*>(archive.ReadObject(&Unit::classUnit));
    return archive;
}

RVA(0x000f562c, 0x37)
void CUnitArchiveBlock::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x000f6d82, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Humanoid*& value) {
    value = static_cast<Humanoid*>(archive.ReadObject(&Humanoid::classHumanoid));
    return archive;
}

RVA(0x000f8a4f, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Diary*& value) {
    value = static_cast<Diary*>(archive.ReadObject(&Diary::classDiary));
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x000f8e4e, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Human*& value) {
    value = static_cast<Human*>(archive.ReadObject(&Human::classHuman));
    return archive;
}

RVA(0x000fa69a, 0x37)
void CSharedArchiveBlock::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

RVA(0x000fa9f5, 0x37)
void CDirectDamagePayload::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

RVA(0x000faac4, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Player*& value) {
    value = static_cast<Player*>(archive.ReadObject(&Player::classPlayer));
    return archive;
}

RVA(0x000fc448, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, SpellEffect*& value) {
    value = static_cast<SpellEffect*>(archive.ReadObject(&SpellEffect::classSpellEffect));
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x000fc59a, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, PointEffect*& value) {
    value = static_cast<PointEffect*>(archive.ReadObject(&PointEffect::classPointEffect));
    return archive;
}

RVA(0x000fc8d7, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, AreaEffect*& value) {
    value = static_cast<AreaEffect*>(archive.ReadObject(&AreaEffect::classAreaEffect));
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x000fda57, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, SpellTransport*& value) {
    value = static_cast<SpellTransport*>(archive.ReadObject(&SpellTransport::classSpellTransport));
    return archive;
}

RVA(0x000fdda2, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Spell*& value) {
    value = static_cast<Spell*>(archive.ReadObject(&Spell::classSpell));
    return archive;
}

RVA(0x00100742, 0xe0)
void Spell::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive << m_values08[0];
        archive << m_values08[1];
        archive << m_values08[2];
        archive << m_value0c;
        archive << reinterpret_cast<UINT>(this); // proven raw pointer identity
    } else {
        archive >> m_values08[0];
        archive >> m_values08[1];
        archive >> m_values08[2];
        archive >> m_value0c;
        UINT value;
        archive >> value;
        g_referenceWorld->m_references.SetAt(
            reinterpret_cast<void*>(value), // proven raw pointer identity
            this
        );
        m_definition = &g_spellDefinitions[m_values08[0]];
    }
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x001008ba, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Spellbook*& value) {
    value = static_cast<Spellbook*>(archive.ReadObject(&Spellbook::classSpellbook));
    return archive;
}

RVA(0x00100c1d, 0xe8)
void Spellbook::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive << m_value18;
        archive << static_cast<UINT>(m_spells.GetSize());
        for (int i = 1; i < m_spells.GetSize(); i++) {
            archive << m_spells[i];
        }
    } else {
        archive >> m_value18;
        UINT size;
        archive >> size;
        m_spells.SetSize(size);
        for (int i = 1; i < m_spells.GetSize(); i++) {
            archive >> m_spells[i];
        }
    }
}

RVA(0x00100d05, 0x9f)
void Effect::Serialize(CArchive& archive) {
    Token::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value3c;
        archive << m_value3d;
        archive << m_value40;
        archive << m_value0c;
    } else {
        archive >> m_value3c;
        archive >> m_value3d;
        archive >> m_value40;
        archive >> m_value0c;
    }
}

RVA(0x00100da4, 0x28)
void Effect_DirectDamage::Serialize(CArchive& archive) {
    Effect::Serialize(archive);
    m_damage.Serialize(archive);
}

RVA(0x00100dcc, 0x63)
void SpellEffect::Serialize(CArchive& archive) {
    Token::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value40;
        archive << m_value41;
    } else {
        archive >> m_value40;
        archive >> m_value41;
    }
}

RVA(0x00100e2f, 0x86)
void SpellTransport::Serialize(CArchive& archive) {
    SpellEffect::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_effect44;
        archive << m_area48;
        archive << m_value4c;
    } else {
        archive >> m_effect44;
        archive >> m_area48;
        archive >> m_value4c;
    }
}

RVA(0x00100efc, 0x7c)
void PointEffect::Serialize(CArchive& archive) {
    SpellEffect::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_effect48;
        archive << m_reference44;
    } else {
        archive >> m_effect48;
        UINT value;
        archive >> value;
        m_reference44 = value;
        ResolveEffectReference(&m_reference44);
    }
}

RVA(0x00100fa5, 0xde)
void AreaEffect::Serialize(CArchive& archive) {
    SpellEffect::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_values48[0];
        archive << m_values48[1];
        archive << m_values48[2];
        archive << m_values48[3];
        archive << m_value4c;
        archive << m_effect44;
    } else {
        archive >> m_values48[0];
        archive >> m_values48[1];
        archive >> m_values48[2];
        archive >> m_values48[3];
        archive >> m_value4c;
        archive >> m_effect44;
    }
}

RVA(0x00101148, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Effect*& value) {
    value = static_cast<Effect*>(archive.ReadObject(&Effect::classEffect));
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x00102b3e, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Effect_DirectDamage*& value) {
    value = static_cast<Effect_DirectDamage*>(
        archive.ReadObject(&Effect_DirectDamage::classEffect_DirectDamage)
    );
    return archive;
}

RVA(0x0010418a, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Building*& value) {
    value = static_cast<Building*>(archive.ReadObject(&Building::classBuilding));
    return archive;
}

RVA(0x00104825, 0x17f)
void Building::Serialize(CArchive& archive) {
    Token::Serialize(archive);
    m_values4a.Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value40;
        archive << m_value42;
        archive << m_value44;
        archive << m_value46;
        archive << m_value48;
        archive << m_value60;
        archive << m_value61;
        archive << m_value64;
        archive << m_value68;
    } else {
        archive >> m_value40;
        archive >> m_value42;
        archive >> m_value44;
        archive >> m_value46;
        archive >> m_value48;
        archive >> m_value60;
        archive >> m_value61;
        archive >> m_value64;
        archive >> m_value68;
        if (m_value40 == 0) {
            m_definition = 0;
        } else {
            m_definition = &g_buildingDefinitions[m_value40];
        }
    }
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x00104a3f, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Outpost*& value) {
    value = static_cast<Outpost*>(archive.ReadObject(&Outpost::classOutpost));
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x00105131, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Tavern*& value) {
    value = static_cast<Tavern*>(archive.ReadObject(&Tavern::classTavern));
    return archive;
}

RVA(0x00105ae4, 0x4a)
void Tavern::Serialize(CArchive& archive) {
    Building::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value9c;
    } else {
        archive >> m_value9c;
    }
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x00105bc6, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Shop*& value) {
    value = static_cast<Shop*>(archive.ReadObject(&Shop::classShop));
    return archive;
}

RVA(0x0010602b, 0x45)
void Shop::Serialize(CArchive& archive) {
    Building::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_value70;
    } else {
        archive >> m_value70;
    }
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x00106108, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, CMultiShopShelf*& value) {
    value =
        static_cast<CMultiShopShelf*>(archive.ReadObject(&CMultiShopShelf::classCMultiShopShelf));
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x001061bf, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, CMultiShopInstance*& value) {
    value = static_cast<CMultiShopInstance*>(
        archive.ReadObject(&CMultiShopInstance::classCMultiShopInstance)
    );
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x00106276, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, CMultiShopTemplate*& value) {
    value = static_cast<CMultiShopTemplate*>(
        archive.ReadObject(&CMultiShopTemplate::classCMultiShopTemplate)
    );
    return archive;
}

RVA(0x00107f85, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Item*& value) {
    value = static_cast<Item*>(archive.ReadObject(&Item::classItem));
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x0010c2c1, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Armor*& value) {
    value = static_cast<Armor*>(archive.ReadObject(&Armor::classArmor));
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x0010ccb0, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Shield*& value) {
    value = static_cast<Shield*>(archive.ReadObject(&Shield::classShield));
    return archive;
}

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x0010d617, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Weapon*& value) {
    value = static_cast<Weapon*>(archive.ReadObject(&Weapon::classWeapon));
    return archive;
}

RVA(0x0010f275, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, Sack*& value) {
    value = static_cast<Sack*>(archive.ReadObject(&Sack::classSack));
    return archive;
}

// AFX.INL COMDATs selected by the original /Od serializer TU.
RVA_COMPGEN(0x00114520, 0x16, ??6@YGAAVCArchive@@AAV0@PBVCObject@@@Z)
RVA_COMPGEN(0x001146e0, 0x19, ??6CArchive@@QAEAAV0@I@Z)
RVA_COMPGEN(0x00114700, 0x43, ??6CArchive@@QAEAAV0@E@Z)
RVA_COMPGEN(0x00114750, 0x43, ??6CArchive@@QAEAAV0@J@Z)
RVA_COMPGEN(0x001147a0, 0x19, ??5CArchive@@QAEAAV0@AAI@Z)
RVA_COMPGEN(0x001147c0, 0x57, ??5CArchive@@QAEAAV0@AAE@Z)
RVA_COMPGEN(0x00114820, 0x57, ??5CArchive@@QAEAAV0@AAJ@Z)

RVA_COMPGEN(0x001176c0, 0x1a, ??6CArchive@@QAEAAV0@F@Z)
RVA_COMPGEN(0x001176e0, 0x45, ??6CArchive@@QAEAAV0@G@Z)
RVA_COMPGEN(0x00117730, 0x19, ??5CArchive@@QAEAAV0@AAF@Z)
RVA_COMPGEN(0x00117750, 0x5b, ??5CArchive@@QAEAAV0@AAG@Z)

RVA_COMPGEN(0x00117860, 0x43, ??6CArchive@@QAEAAV0@K@Z)
RVA_COMPGEN(0x001178b0, 0x59, ??5CArchive@@QAEAAV0@AAK@Z)

RVA_COMPGEN(0x0011a490, 0x19, ??A?$CArray@VCTableLineBaseOnly@@AAV1@@@QAEAAVCTableLineBaseOnly@@H@Z)

RVA_COMPGEN(0x0011a830, 0x19, ??A?$CArray@VCTableLineLabel@@AAV1@@@QAEAAVCTableLineLabel@@H@Z)

RVA_COMPGEN(0x0011a990, 0x11, ?GetSize@?$CArray@PAVSpell@@PAV1@@@QBEHXZ)
RVA_COMPGEN(0x0011a9b0, 0x21a, ?SetSize@?$CArray@PAVSpell@@PAV1@@@QAEXHH@Z)
RVA_COMPGEN(0x0011abd0, 0x19, ??A?$CArray@PAVSpell@@PAV1@@@QAEAAPAVSpell@@H@Z)

RVA(0x00120eb0, 0x3a)
void ResolveEffectReference(UINT* value) {
    void* result;
    if (g_referenceWorld->m_references
            .Lookup(reinterpret_cast<void*>(*value), result)) { // proven raw pointer identity
        *value = reinterpret_cast<UINT>(result);                // proven raw pointer identity
    } else {
        *value = 0;
    }
}

RVA(0x00121440, 0x3a)
void ResolveTokenReference(UINT* value) {
    void* result;
    if (g_referenceWorld->m_references
            .Lookup(reinterpret_cast<void*>(*value), result)) { // proven raw pointer identity
        *value = reinterpret_cast<UINT>(result);                // proven raw pointer identity
    } else {
        *value = 0;
    }
}

RVA(0x00121480, 0x3a)
void ResolvePlayerReference(UINT* value) {
    void* result;
    if (g_referenceWorld->m_references
            .Lookup(reinterpret_cast<void*>(*value), result)) { // proven raw pointer identity
        *value = reinterpret_cast<UINT>(result);                // proven raw pointer identity
    } else {
        *value = 0;
    }
}

RVA_COMPGEN(0x00123350, 0x1b, ?ElementAt@?$CArray@VCTableLineBaseOnly@@AAV1@@@QAEAAVCTableLineBaseOnly@@H@Z)
RVA_COMPGEN(0x001234d0, 0x1b, ?ElementAt@?$CArray@VCTableLineLabel@@AAV1@@@QAEAAVCTableLineLabel@@H@Z)
RVA_COMPGEN(0x001236c0, 0x19, ?ElementAt@?$CArray@PAVSpell@@PAV1@@@QAEAAPAVSpell@@H@Z)

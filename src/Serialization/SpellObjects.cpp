#include <rva.h>

#include <Serialization/SpellObjects.h>

DATA(0x001cd6b0)
CReferenceWorld* g_referenceWorld;

DATA(0x0022c738)
UINT g_seenTokenIds[0x800];

RVA(0x000d9f67, 0x3f)
static void MarkTokenIdSeen(WORD value) {
    g_seenTokenIds[value >> 5] |= 1 << (value & 31);
}

RVA(0x000fa9f5, 0x37)
void CDirectDamagePayload::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
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

// AFX.INL COMDATs selected by the original /Od serializer TU.
RVA_COMPGEN(0x00114520, 0x16, ??6@YGAAVCArchive@@AAV0@PBVCObject@@@Z)
RVA_COMPGEN(0x001146e0, 0x19, ??6CArchive@@QAEAAV0@I@Z)
RVA_COMPGEN(0x00114700, 0x43, ??6CArchive@@QAEAAV0@E@Z)
RVA_COMPGEN(0x00114750, 0x43, ??6CArchive@@QAEAAV0@J@Z)
RVA_COMPGEN(0x001147a0, 0x19, ??5CArchive@@QAEAAV0@AAI@Z)
RVA_COMPGEN(0x001147c0, 0x57, ??5CArchive@@QAEAAV0@AAE@Z)
RVA_COMPGEN(0x00114820, 0x57, ??5CArchive@@QAEAAV0@AAJ@Z)

RVA_COMPGEN(0x001176a0, 0x1c, ?SetAt@CMapPtrToPtr@@QAEXPAX0@Z)
RVA_COMPGEN(0x001176c0, 0x1a, ??6CArchive@@QAEAAV0@F@Z)
RVA_COMPGEN(0x001176e0, 0x45, ??6CArchive@@QAEAAV0@G@Z)
RVA_COMPGEN(0x00117730, 0x19, ??5CArchive@@QAEAAV0@AAF@Z)
RVA_COMPGEN(0x00117750, 0x5b, ??5CArchive@@QAEAAV0@AAG@Z)

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

RVA_COMPGEN(0x001236c0, 0x19, ?ElementAt@?$CArray@PAVSpell@@PAV1@@@QAEAAPAVSpell@@H@Z)

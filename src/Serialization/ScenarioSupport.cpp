#include <rva.h>

#include <Serialization/SpellObjects.h>

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

RVA_COMPGEN(0x001176a0, 0x1c, ?SetAt@CMapPtrToPtr@@QAEXPAX0@Z)

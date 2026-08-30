#include <rva.h>

#include <Serialization/ArchiveObjects.h>

// AFX.INL provides this COMDAT when the /Od serializers call IsStoring.
RVA_COMPGEN(0x00049770, 0x19, ?IsStoring@CArchive@@QBEHXZ)

RVA(0x000df278, 0x4e)
void TableLine::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive << m_name;
    } else {
        archive >> m_name;
    }
    m_value.Serialize(archive);
}

RVA(0x000dffcd, 0x19)
void CTableLineBaseOnly::Serialize(CArchive& archive) {
    TableLine::Serialize(archive);
}

RVA(0x00111b15, 0x20)
void CSerializableObjectHolder::Serialize(CArchive& archive) {
    m_value.Serialize(archive);
}

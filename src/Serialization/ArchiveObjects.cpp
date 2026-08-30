#include <rva.h>

#include <Serialization/ArchiveObjects.h>

// AFXCOLL.INL emits these out-of-line COMDATs because this TU disables MFC
// inlining. They are the exact access seam used by the fixed CString loops.
RVA_COMPGEN(0x00047a80, 0x19, ??ACStringArray@@QAEAAVCString@@H@Z)
RVA_COMPGEN(0x00047aa0, 0x19, ?ElementAt@CStringArray@@QAEAAVCString@@H@Z)

// AFX.INL provides this COMDAT when the /Od serializers call IsStoring.
RVA_COMPGEN(0x00049770, 0x19, ?IsStoring@CArchive@@QBEHXZ)

// @dead-code
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x000de85b, 0x1c)
CArchive& AFXAPI operator>>(CArchive& archive, TableLine*& value) {
    value = static_cast<TableLine*>(archive.ReadObject(&TableLine::classTableLine));
    return archive;
}

RVA(0x000df278, 0x4e)
void TableLine::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive << m_name;
    } else {
        archive >> m_name;
    }
    m_values.Serialize(archive);
}

RVA(0x000df2c6, 0x5c)
void CTableLineWordBlock::Serialize(CArchive& archive) {
    TableLine::Serialize(archive);
    if (archive.IsStoring()) {
        archive.Write(m_words, sizeof(m_words));
    } else {
        archive.Read(m_words, sizeof(m_words));
    }
    m_strings.Serialize(archive);
}

RVA(0x000df322, 0x5d)
void CTableLineRawBlock::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive << m_name;
        archive.Write(m_bytes, sizeof(m_bytes));
    } else {
        archive >> m_name;
        archive.Read(m_bytes, sizeof(m_bytes));
    }
}

RVA(0x000df42a, 0x69)
void CTableLineWordBlockLabel::Serialize(CArchive& archive) {
    TableLine::Serialize(archive);
    if (archive.IsStoring()) {
        archive.Write(m_words, sizeof(BYTE));
        archive << m_label;
    } else {
        archive.Read(m_words, sizeof(BYTE));
        archive >> m_label;
    }
}

RVA(0x000df63a, 0x8f)
void CTableLineStringPair::Serialize(CArchive& archive) {
    TableLine::Serialize(archive);
    if (archive.IsStoring()) {
        for (int i = 0; i < 2; i++) {
            archive << m_strings[i];
        }
    } else {
        for (int i = 0; i < 2; i++) {
            archive >> m_strings[i];
        }
    }
}

RVA(0x000dfe42, 0x8f)
void CTableLineStringDecade::Serialize(CArchive& archive) {
    TableLine::Serialize(archive);
    if (archive.IsStoring()) {
        for (int i = 0; i < 10; i++) {
            archive << m_strings[i];
        }
    } else {
        for (int i = 0; i < 10; i++) {
            archive >> m_strings[i];
        }
    }
}

RVA(0x000dffcd, 0x19)
void CTableLineBaseOnly::Serialize(CArchive& archive) {
    TableLine::Serialize(archive);
}

RVA(0x000e03d2, 0x47)
void CTableLineLabel::Serialize(CArchive& archive) {
    TableLine::Serialize(archive);
    if (archive.IsStoring()) {
        archive << m_label;
    } else {
        archive >> m_label;
    }
}

RVA(0x00111b15, 0x20)
void CSerializableObjectHolder::Serialize(CArchive& archive) {
    m_value.Serialize(archive);
}

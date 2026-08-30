#include <rva.h>

#include <Serialization/ReferenceRecords.h>

// @dead-code: retained because FPO gives an exact standalone serializer.
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x0013db00, 0x23)
void CReferenceRecordLarge::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

// @dead-code: retained because FPO gives an exact standalone serializer.
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x0013dbc0, 0x23)
void CReferenceRecordCompact::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

// @dead-code: retained because FPO gives an exact standalone serializer.
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x0013dc80, 0x23)
void CRawArchiveRecord::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

// @dead-code: retained because FPO gives an exact standalone serializer.
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x0013dcc0, 0xd1)
void CArchiveListPairRecord::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
        m_triples->Serialize(archive);
        m_dwords->Serialize(archive);
    } else {
        delete m_triples;
        delete m_dwords;
        archive.Read(this, sizeof(*this));
        m_triples = new CArchiveTripleList;
        m_dwords = new CArchiveDwordList;
        m_triples->Serialize(archive);
        m_dwords->Serialize(archive);
    }
}

// The following located list methods supply the exact virtual identities used
// by CArchiveListPairRecord.  Their bodies are separate serde work and remain
// deliberately unpromoted here.
void CArchiveTripleList::Serialize(CArchive&) {}

CArchiveDwordList::~CArchiveDwordList() {}

void CArchiveDwordList::Serialize(CArchive&) {}

CArchiveTripleList::~CArchiveTripleList() {}

#include <rva.h>

#include <Serialization/ReferenceRecords.h>

CReferenceRecordLarge::~CReferenceRecordLarge() {}

CReferenceRecordCompact::CReferenceRecordCompact() {
    memset(m_record, 0, sizeof(m_record));
}

CReferenceRecordCompact::~CReferenceRecordCompact() {}

CRawArchiveRecord::~CRawArchiveRecord() {}

CArchiveListPairRecord::CArchiveListPairRecord() {
    memset(this, 0, sizeof(*this));
    m_triples = new CArchiveTripleList;
    m_dwords = new CArchiveDwordList;
}

CArchiveListPairRecord::CArchiveListPairRecord(const CArchiveListPairRecord& other) {
    memcpy(this, &other, sizeof(*this));
    m_triples = new CArchiveTripleList;
    m_dwords = new CArchiveDwordList;

    POSITION position = other.m_triples->GetHeadPosition();
    while (position != NULL) {
        m_triples->AddTail(other.m_triples->GetNext(position));
    }

    position = other.m_dwords->GetHeadPosition();
    while (position != NULL) {
        m_dwords->AddTail(other.m_dwords->GetNext(position));
    }
}

CArchiveListPairRecord::~CArchiveListPairRecord() {
    delete m_triples;
    delete m_dwords;
}

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

RVA_COMPGEN(0x0013ec20, 0x205, ?Serialize@?$CMap@KKKK@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0013eec0, 0x205, ?Serialize@?$CMap@PAXPAXKK@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0013f160, 0x205, ?Serialize@?$CMap@KKPAXPAX@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0013f450, 0x205, ?Serialize@?$CMap@PAXPAXPAXPAX@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0013f6c0, 0x188, ?Serialize@?$CArray@KK@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0013f850, 0xff, ?Serialize@?$CList@VCReferenceRecordLarge@@V1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0013fb60, 0x23b, ?Serialize@?$CArray@VCReferenceRecordCompact@@AAV1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0013fda0, 0x187, ?Serialize@?$CList@VCArchiveListPairRecord@@V1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0013ff30, 0x103, ?Serialize@?$CList@VCRawArchiveRecord@@V1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x001400e0, 0x118, ?Serialize@?$CList@PAXPAX@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00140270, 0x115, ?Serialize@?$CList@EE@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x001403f0, 0x17f, ?Serialize@?$CArray@EE@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x001405e0, 0x118, ?Serialize@?$CList@PAVCObject@@PAV1@@@UAEXAAVCArchive@@@Z)

// Keep each retail-proven specialization live without forcing unrelated
// template members (for example Find/operator==) into this object.
void InstantiateReferenceRecordContainers(CArchive& archive) {
    CArchiveDwordMap dwordMap;
    CArchivePointerDwordMap pointerDwordMap;
    CArchiveDwordPointerMap dwordPointerMap;
    CArchivePointerMap pointerMap;
    CArchiveDwordArray dwordArray;
    CArchiveLargeRecordList largeRecordList;
    CArchiveCompactRecordArray compactRecordArray;
    CArchiveListPairList pairList;
    CArchiveTripleList tripleList;
    CArchiveDwordList dwordList;
    CArchiveByteList byteList;
    CArchiveByteArray byteArray;
    CArchivePointerList pointerList;

    dwordMap.Serialize(archive);
    pointerDwordMap.Serialize(archive);
    dwordPointerMap.Serialize(archive);
    pointerMap.Serialize(archive);
    dwordArray.Serialize(archive);
    largeRecordList.Serialize(archive);
    compactRecordArray.Serialize(archive);
    pairList.Serialize(archive);
    tripleList.Serialize(archive);
    dwordList.Serialize(archive);
    byteList.Serialize(archive);
    byteArray.Serialize(archive);
    pointerList.Serialize(archive);
}

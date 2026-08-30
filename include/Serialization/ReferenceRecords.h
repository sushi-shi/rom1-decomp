#ifndef ROM1_SERIALIZATION_REFERENCERECORDS_H
#define ROM1_SERIALIZATION_REFERENCERECORDS_H

#include <MfcNoInline.h>

#include <afxtempl.h>

// Retail has no surviving names for these complete-object records.  Their
// sizes, construction, and raw archive treatment are fixed by the adjacent
// CArray/CList instantiations and reference-remapping methods.
class CReferenceRecordLarge {
public:
    CReferenceRecordLarge() {
        memset(this, 0, sizeof(*this));
        m_enabled = 1;
    }
    ~CReferenceRecordLarge();
    void Serialize(CArchive& archive);

private:
    BYTE m_record[0x48];
    DWORD m_enabled;
    DWORD m_tail;
};

class CReferenceRecordCompact {
public:
    CReferenceRecordCompact();
    ~CReferenceRecordCompact();
    void Serialize(CArchive& archive);

private:
    BYTE m_record[0x48];
};

class CRawArchiveRecord {
public:
    CRawArchiveRecord() {
        m_values[0] = 0;
        m_values[1] = 0;
        m_values[2] = 0;
    }
    ~CRawArchiveRecord();
    void Serialize(CArchive& archive);

private:
    DWORD m_values[3];
};

// These aliases preserve only facts visible in retail: element widths,
// by-value/by-reference template arguments, and the shared MFC layouts.
typedef CList<CRawArchiveRecord, CRawArchiveRecord> CArchiveTripleList;
typedef CList<void*, void*> CArchiveDwordList;

// This complete 24-byte record owns one list of each element width.  Retail
// stores the raw record before dispatching the two list serializers, replacing
// both stale pointer values with newly allocated lists while loading.
class CArchiveListPairRecord {
public:
    CArchiveListPairRecord();
    CArchiveListPairRecord(const CArchiveListPairRecord& other);
    ~CArchiveListPairRecord();
    void Serialize(CArchive& archive);

private:
    CArchiveTripleList* m_triples;
    CArchiveDwordList* m_dwords;
    BYTE m_recordTail[0x10];
};

typedef CMap<DWORD, DWORD, DWORD, DWORD> CArchiveDwordMap;
typedef CMap<void*, void*, DWORD, DWORD> CArchivePointerDwordMap;
typedef CMap<DWORD, DWORD, void*, void*> CArchiveDwordPointerMap;
typedef CMap<void*, void*, void*, void*> CArchivePointerMap;

typedef CArray<DWORD, DWORD> CArchiveDwordArray;
typedef CList<CReferenceRecordLarge, CReferenceRecordLarge> CArchiveLargeRecordList;
typedef CArray<CReferenceRecordCompact, CReferenceRecordCompact&> CArchiveCompactRecordArray;
typedef CList<CArchiveListPairRecord, CArchiveListPairRecord> CArchiveListPairList;
typedef CList<BYTE, BYTE> CArchiveByteList;
typedef CArray<BYTE, BYTE> CArchiveByteArray;

// The last serializer is byte-identical to the DWORD list but is a distinct
// template specialization in retail; its users store pointer-sized values.
typedef CList<CObject*, CObject*> CArchivePointerList;

#endif // ROM1_SERIALIZATION_REFERENCERECORDS_H

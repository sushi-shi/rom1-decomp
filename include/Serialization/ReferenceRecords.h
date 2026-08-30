#ifndef ROM1_SERIALIZATION_REFERENCERECORDS_H
#define ROM1_SERIALIZATION_REFERENCERECORDS_H

#include <MfcNoInline.h>

// No retail name survives for these three complete-object records.  Their
// exact sizes and raw archive treatment are fixed by the Serialize bodies;
// the two larger records are distinguished by adjacent reference-remapping
// methods that access three object pointers at +0x30, +0x34, and +0x38.
class CReferenceRecordLarge {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_record[0x50];
};

class CReferenceRecordCompact {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_record[0x48];
};

class CRawArchiveRecord {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_record[0x0c];
};

// Two game-owned list classes use the contemporary MFC list layout but return
// CObject's runtime-class record, proving that they are distinct non-runtime-
// class types.  Their slot-2 bodies fix 12-byte and DWORD element widths.
class CArchiveTripleList : public CObject {
public:
    explicit CArchiveTripleList(int blockSize = 10) {
        m_count = 0;
        m_head = m_tail = m_free = 0;
        m_blocks = 0;
        m_blockSize = blockSize;
    }

    virtual ~CArchiveTripleList();
    virtual void Serialize(CArchive& archive);

private:
    struct Node;

    Node* m_head;
    Node* m_tail;
    int m_count;
    Node* m_free;
    CPlex* m_blocks;
    int m_blockSize;
};

class CArchiveDwordList : public CObject {
public:
    explicit CArchiveDwordList(int blockSize = 10) {
        m_count = 0;
        m_head = m_tail = m_free = 0;
        m_blocks = 0;
        m_blockSize = blockSize;
    }

    virtual ~CArchiveDwordList();
    virtual void Serialize(CArchive& archive);

private:
    struct Node;

    Node* m_head;
    Node* m_tail;
    int m_count;
    Node* m_free;
    CPlex* m_blocks;
    int m_blockSize;
};

// This complete 24-byte record owns one list of each element width.  Retail
// stores the raw record before dispatching the two list serializers, replacing
// both stale pointer values with newly allocated lists while loading.
class CArchiveListPairRecord {
public:
    void Serialize(CArchive& archive);

private:
    CArchiveTripleList* m_triples;
    CArchiveDwordList* m_dwords;
    BYTE m_recordTail[0x10];
};

#endif // ROM1_SERIALIZATION_REFERENCERECORDS_H

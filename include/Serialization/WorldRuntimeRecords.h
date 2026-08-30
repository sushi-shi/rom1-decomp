#ifndef ROM1_SERIALIZATION_WORLDRUNTIMERECORDS_H
#define ROM1_SERIALIZATION_WORLDRUNTIMERECORDS_H

#include <MfcNoInline.h>

#include <afxtempl.h>

// Player+0x30 owns a separately allocated 32-byte record with this exact raw
// archive contract.  No original class name survives.
class CPlayerArchiveBlock {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_bytes[0x20];
};

// Two separately allocated game-owned records contain raw state followed by
// a CList<WORD, WORD> pointer.  Their owning serializers at 0x110577 and
// 0x111997 prove the record extents and pointer offsets; no class names survive.
class CWordListRecordLarge {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_record[0x90];
    CList<WORD, WORD>* m_words;
};

class CWordListRecordCompact {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_record[0x4c];
    CList<WORD, WORD>* m_words;
};

#endif // ROM1_SERIALIZATION_WORLDRUNTIMERECORDS_H

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

// Unit owns one separately allocated record with this complete raw archive
// contract. Retail fixes the 0xb4-byte extent but preserves no source name.
class CUnitRawArchiveRecord {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_bytes[0xb4];
};

// Two optimized collection serializers used by game-owned world state retain
// four-byte element widths and a WORD map key, but no semantic element names.
struct CUnitMapValue {
    DWORD m_value;
};

struct CUnitListValue {
    BYTE m_bytes[4];
};

typedef CMap<WORD, WORD, CUnitMapValue, CUnitMapValue> CUnitValueMap;
typedef CList<CUnitListValue, CUnitListValue> CUnitValueList;

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
    CWordListRecordCompact();
    void Serialize(CArchive& archive);

private:
    BYTE m_record[0x4c];
    CList<WORD, WORD>* m_words;
};

#endif // ROM1_SERIALIZATION_WORLDRUNTIMERECORDS_H

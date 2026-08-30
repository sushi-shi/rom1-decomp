#ifndef ROM1_SERIALIZATION_ARCHIVEARRAYS_H
#define ROM1_SERIALIZATION_ARCHIVEARRAYS_H

#include <MfcNoInline.h>

#include <afxtempl.h>

// This family is serialized only through MFC collection templates.  Retail
// therefore preserves each complete element size and which collections share
// an element type, but not the original game-owned source names.  Keep one
// canonical declaration for every distinct recovered identity until stronger
// field-use evidence supplies semantic names.
// @identity-TODO: recover the original record names and fields.
struct CLinkedCollectionValue {
    BYTE m_bytes[4];
};

struct CQueuedCollectionValue {
    BYTE m_bytes[4];
};

struct CSharedCollectionValue {
    BYTE m_bytes[4];
};

struct CLargeCollectionRecord {
    BYTE m_bytes[0x68];
};

struct CNamedCollectionRecord {
    BYTE m_bytes[0x3c];
};

struct CFixedCollectionRecord {
    BYTE m_bytes[0x40];
};

struct CCompactCollectionRecord {
    BYTE m_bytes[0x1c];
};

struct CPrimaryStateRecord {
    BYTE m_bytes[0x30];
};

struct CSecondaryStateRecord {
    BYTE m_bytes[0x30];
};

struct CTertiaryStateRecord {
    BYTE m_bytes[0x1c];
};

struct CCollectionHandle {
    BYTE m_bytes[4];
};

struct CMapValueHandle {
    BYTE m_bytes[4];
};

struct CMapObjectHandle {
    BYTE m_bytes[4];
};

struct CMapRecordHandle {
    BYTE m_bytes[4];
};

struct CSharedMapHandle {
    BYTE m_bytes[4];
};

struct CMapTailHandle {
    BYTE m_bytes[4];
};

// Retail construction/destruction and member-use sites prove a 12-byte record
// made from exactly three CStrings.  No surviving runtime-class or
// address-bearing string preserves the record's original source name.
class CStringTriple {
private:
    CString m_first;
    CString m_second;
    CString m_third;
};

typedef CArray<CStringArray*, CStringArray*> CStringArrayPointerArray;
typedef CArray<CStringTriple*, CStringTriple*> CStringTriplePointerArray;
typedef CArray<WIN32_FIND_DATA, WIN32_FIND_DATA> Win32FindDataArray;
// @identity-TODO: element use proves pointers, but the pointee identity and
// complete layout do not survive in the current executable evidence.
typedef CArray<void*, void*> OpaquePointerArray;

#endif // ROM1_SERIALIZATION_ARCHIVEARRAYS_H

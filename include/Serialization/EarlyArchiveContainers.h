#ifndef ROM1_SERIALIZATION_EARLYARCHIVECONTAINERS_H
#define ROM1_SERIALIZATION_EARLYARCHIVECONTAINERS_H

#include <Mfc.h>

#include <afxtempl.h>

// These collection types are embedded in the large game-owned owner whose
// constructor/destructor touch the corresponding vtables.  Retail preserves
// their complete element widths and lifecycle but no source-level names.
// Keep distinct four-byte identities where the executable has distinct
// CArray vtables; merging them would erase proven type separation.
// @identity-TODO: recover the original element and owner names.
struct CEarlyArchiveHandle {
    DWORD m_value;
};

struct CEarlyArchiveValue {
    DWORD m_value;
};

struct CEarlyArchiveReference {
    DWORD m_value;
};

struct CEarlyArchiveToken {
    DWORD m_value;
};

struct CEarlyArchiveBlock {
    CEarlyArchiveBlock() {}

    BYTE m_bytes[0x10];
};

// The element constructor at 0x055e40 and destructor at 0x055fa0 prove the
// CString prefix and the initialized DWORDs.  The remaining bytes have no
// independently recovered field identity yet.
class CEarlyArchiveTextRecord {
public:
    CEarlyArchiveTextRecord();

private:
    CString m_name;
    BYTE m_reserved04[0x10];
    DWORD m_value14;
    DWORD m_value18;
    BYTE m_reserved1c[0x08];
};

typedef CArray<CEarlyArchiveHandle, CEarlyArchiveHandle> CEarlyArchiveHandleArray;
typedef CArray<WORD, WORD> CEarlyArchiveWordArray;
typedef CArray<CEarlyArchiveValue, CEarlyArchiveValue> CEarlyArchiveValueArray;
typedef CArray<CEarlyArchiveBlock, CEarlyArchiveBlock&> CEarlyArchiveBlockArray;
typedef CArray<CEarlyArchiveReference, CEarlyArchiveReference> CEarlyArchiveReferenceArray;
typedef CArray<CEarlyArchiveTextRecord, CEarlyArchiveTextRecord&> CEarlyArchiveTextRecordArray;
typedef CArray<CEarlyArchiveToken, CEarlyArchiveToken> CEarlyArchiveTokenArray;

typedef CMap<WORD, WORD&, DWORD, DWORD&> CEarlyArchiveReferenceMap;
typedef CMap<WORD, WORD, DWORD, DWORD> CEarlyArchiveValueMap;

#endif // ROM1_SERIALIZATION_EARLYARCHIVECONTAINERS_H

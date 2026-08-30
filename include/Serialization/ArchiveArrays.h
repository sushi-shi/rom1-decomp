#ifndef ROM1_SERIALIZATION_ARCHIVEARRAYS_H
#define ROM1_SERIALIZATION_ARCHIVEARRAYS_H

#include <MfcNoInline.h>

#include <afxtempl.h>

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

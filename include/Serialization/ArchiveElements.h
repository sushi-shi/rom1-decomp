#ifndef ROM1_SERIALIZATION_ARCHIVEELEMENTS_H
#define ROM1_SERIALIZATION_ARCHIVEELEMENTS_H

#include <MfcNoInline.h>

#include <afxtempl.h>

// Two distinct four-byte element types are proved by their neighboring
// CArray method clusters.  Their original names and member identities do not
// survive, so only the exact raw extent is modeled here.
struct CArchiveElement4Primary {
    BYTE m_bytes[4];
};

struct CArchiveElement4Secondary {
    BYTE m_bytes[4];
};

// Two game-owned resource subsystems keep distinct arrays of raw pointer
// handles. Retail append/set callsites prove pointer words passed by value,
// while the complete pointee layouts and original class names do not survive.
struct CResourceOwnedObjectHandle {
    void* m_object;
};

struct CResourceIndexedObjectHandle {
    void* m_object;
};

typedef CArray<CResourceOwnedObjectHandle, CResourceOwnedObjectHandle> CResourceOwnedObjectArray;
typedef CArray<CResourceIndexedObjectHandle, CResourceIndexedObjectHandle>
    CResourceIndexedObjectArray;

#endif // ROM1_SERIALIZATION_ARCHIVEELEMENTS_H

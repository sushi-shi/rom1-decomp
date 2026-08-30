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

#endif // ROM1_SERIALIZATION_ARCHIVEELEMENTS_H

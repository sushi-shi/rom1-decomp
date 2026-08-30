#ifndef ROM1_SERIALIZATION_STRUCTUREARCHIVECONTAINERS_H
#define ROM1_SERIALIZATION_STRUCTUREARCHIVECONTAINERS_H

#include <MfcNoInline.h>

#include <afxtempl.h>

// These seven collection specializations are emitted together by the
// structure/resource translation unit.  Retail proves seven distinct CArray
// vtables and four-byte element widths, but preserves no type-bearing RTTI or
// non-template caller from which the original element names can be recovered.
// Keep the identities distinct and the payloads opaque until their owners are
// reconstructed; merging them would erase the seven independently proven
// source types.
// @identity-TODO: recover the original element and owner names.
struct CStructureArchiveHandle {
    DWORD m_value;
};

struct CStructureArchiveValue {
    DWORD m_value;
};

struct CStructureArchiveReference {
    DWORD m_value;
};

struct CStructureArchiveToken {
    DWORD m_value;
};

struct CStructureArchiveIndex {
    DWORD m_value;
};

struct CStructureArchiveKey {
    DWORD m_value;
};

struct CStructureArchiveLink {
    DWORD m_value;
};

typedef CArray<CStructureArchiveHandle, CStructureArchiveHandle&> CStructureArchiveHandleArray;
typedef CArray<CStructureArchiveValue, CStructureArchiveValue&> CStructureArchiveValueArray;
typedef CArray<CStructureArchiveReference, CStructureArchiveReference&>
    CStructureArchiveReferenceArray;
typedef CArray<CStructureArchiveToken, CStructureArchiveToken&> CStructureArchiveTokenArray;
typedef CArray<CStructureArchiveIndex, CStructureArchiveIndex&> CStructureArchiveIndexArray;
typedef CArray<CStructureArchiveKey, CStructureArchiveKey&> CStructureArchiveKeyArray;
typedef CArray<CStructureArchiveLink, CStructureArchiveLink&> CStructureArchiveLinkArray;

#endif // ROM1_SERIALIZATION_STRUCTUREARCHIVECONTAINERS_H

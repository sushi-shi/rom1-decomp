#include <rva.h>

#include <Serialization/ArchiveElements.h>

RVA_COMPGEN(0x000ae2e0, 0x3b, ?SerializeElements@@YGXAAVCArchive@@PAUCArchiveElement4Primary@@H@Z)

RVA_COMPGEN(0x000ae3b0, 0x3b, ?SerializeElements@@YGXAAVCArchive@@PAUCArchiveElement4Secondary@@H@Z)

RVA_COMPGEN(0x000c8600, 0x68, ?Serialize@?$CArray@UCResourceOwnedObjectHandle@@U1@@@UAEXAAVCArchive@@@Z)
template void CResourceOwnedObjectArray::Serialize(CArchive& archive);

RVA_COMPGEN(0x000c8720, 0x21a, ?SetSize@?$CArray@UCResourceIndexedObjectHandle@@U1@@@QAEXHH@Z)
RVA_COMPGEN(0x000c8a40, 0x68, ?Serialize@?$CArray@UCResourceIndexedObjectHandle@@U1@@@UAEXAAVCArchive@@@Z)
template void CResourceIndexedObjectArray::Serialize(CArchive& archive);

RVA_COMPGEN(0x000c8c30, 0x21a, ?SetSize@?$CArray@UCResourceOwnedObjectHandle@@U1@@@QAEXHH@Z)
RVA_COMPGEN(0x000c8ee0, 0x3b, ?SerializeElements@@YGXAAVCArchive@@PAUCResourceOwnedObjectHandle@@H@Z)
RVA_COMPGEN(0x000c8fe0, 0x3b, ?SerializeElements@@YGXAAVCArchive@@PAUCResourceIndexedObjectHandle@@H@Z)

template void AFXAPI SerializeElements<CArchiveElement4Primary>(
    CArchive& archive,
    CArchiveElement4Primary* elements,
    int count
);

template void AFXAPI SerializeElements<CArchiveElement4Secondary>(
    CArchive& archive,
    CArchiveElement4Secondary* elements,
    int count
);

template void AFXAPI SerializeElements<CResourceOwnedObjectHandle>(
    CArchive& archive,
    CResourceOwnedObjectHandle* elements,
    int count
);

template void AFXAPI SerializeElements<CResourceIndexedObjectHandle>(
    CArchive& archive,
    CResourceIndexedObjectHandle* elements,
    int count
);

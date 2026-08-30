#include <rva.h>

#include <Serialization/ArchiveElements.h>

RVA_COMPGEN(0x000ae2e0, 0x3b, ?SerializeElements@@YGXAAVCArchive@@PAUCArchiveElement4Primary@@H@Z)

RVA_COMPGEN(0x000ae3b0, 0x3b, ?SerializeElements@@YGXAAVCArchive@@PAUCArchiveElement4Secondary@@H@Z)

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

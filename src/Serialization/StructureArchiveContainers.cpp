#include <rva.h>

#include <Serialization/StructureArchiveContainers.h>

// clang-format off
RVA_COMPGEN(0x0006f6a0, 0x188, ?Serialize@?$CArray@UCStructureArchiveHandle@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0006f8b0, 0x188, ?Serialize@?$CArray@UCStructureArchiveValue@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0006fac0, 0x188, ?Serialize@?$CArray@UCStructureArchiveReference@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0006fcd0, 0x188, ?Serialize@?$CArray@UCStructureArchiveToken@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0006fee0, 0x188, ?Serialize@?$CArray@UCStructureArchiveIndex@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x000700f0, 0x188, ?Serialize@?$CArray@UCStructureArchiveKey@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00070300, 0x188, ?Serialize@?$CArray@UCStructureArchiveLink@@AAU1@@@UAEXAAVCArchive@@@Z)
// clang-format on

template void
CArray<CStructureArchiveHandle, CStructureArchiveHandle&>::Serialize(CArchive& archive);
template void CArray<CStructureArchiveValue, CStructureArchiveValue&>::Serialize(CArchive& archive);
template void
CArray<CStructureArchiveReference, CStructureArchiveReference&>::Serialize(CArchive& archive);
template void CArray<CStructureArchiveToken, CStructureArchiveToken&>::Serialize(CArchive& archive);
template void CArray<CStructureArchiveIndex, CStructureArchiveIndex&>::Serialize(CArchive& archive);
template void CArray<CStructureArchiveKey, CStructureArchiveKey&>::Serialize(CArchive& archive);
template void CArray<CStructureArchiveLink, CStructureArchiveLink&>::Serialize(CArchive& archive);

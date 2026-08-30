#include <rva.h>

#include <Serialization/EarlyArchiveContainers.h>

// clang-format off
RVA_COMPGEN(0x000019f0, 0x188, ?Serialize@?$CArray@UCEarlyArchiveHandle@@U1@@@UAEXAAVCArchive@@@Z)
// clang-format on

template void CArray<CEarlyArchiveHandle, CEarlyArchiveHandle>::Serialize(CArchive& archive);

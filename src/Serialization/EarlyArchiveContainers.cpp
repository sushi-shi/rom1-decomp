#include <rva.h>

#include <Serialization/EarlyArchiveContainers.h>

// clang-format off
RVA_COMPGEN(0x00023930, 0x361, ?Serialize@?$CArray@GG@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00023d40, 0x369, ?Serialize@?$CArray@UCEarlyArchiveValue@@U1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00024150, 0x3c4, ?Serialize@?$CArray@UCEarlyArchiveBlock@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x000245c0, 0x369, ?Serialize@?$CArray@UCEarlyArchiveReference@@U1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00024fb0, 0x43e, ?Serialize@?$CMap@GGKK@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x000256f0, 0x428, ?Serialize@?$CMap@GAAGKAAK@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00025be0, 0x396, ?Serialize@?$CArray@VCEarlyArchiveTextRecord@@AAV1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x000260a0, 0x369, ?Serialize@?$CArray@UCEarlyArchiveToken@@U1@@@UAEXAAVCArchive@@@Z)
// clang-format on

CEarlyArchiveTextRecord::CEarlyArchiveTextRecord() : m_value14(0), m_value18(1) {}

template void CArray<WORD, WORD>::Serialize(CArchive& archive);
template void CArray<CEarlyArchiveValue, CEarlyArchiveValue>::Serialize(CArchive& archive);
template void CArray<CEarlyArchiveBlock, CEarlyArchiveBlock&>::Serialize(CArchive& archive);
template void CArray<CEarlyArchiveReference, CEarlyArchiveReference>::Serialize(CArchive& archive);
template void CMap<WORD, WORD&, DWORD, DWORD&>::Serialize(CArchive& archive);
template void CMap<WORD, WORD, DWORD, DWORD>::Serialize(CArchive& archive);
template void
CArray<CEarlyArchiveTextRecord, CEarlyArchiveTextRecord&>::Serialize(CArchive& archive);
template void CArray<CEarlyArchiveToken, CEarlyArchiveToken>::Serialize(CArchive& archive);

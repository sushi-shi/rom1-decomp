#include <rva.h>

#include <Serialization/ArchiveArrays.h>

RVA_COMPGEN(0x00049420, 0x21a, ?SetSize@?$CArray@PAVCStringArray@@PAV1@@@QAEXHH@Z)
RVA_COMPGEN(0x00049700, 0x68, ?Serialize@?$CArray@PAVCStringArray@@PAV1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x000498d0, 0x68, ?Serialize@?$CArray@PAVCStringTriple@@PAV1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00049ba0, 0x68, ?Serialize@?$CArray@U_WIN32_FIND_DATAA@@U1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00049ca0, 0x68, ?Serialize@?$CArray@PAXPAX@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x0004a230, 0x24, ?DestructElements@@YGXPAPAVCStringArray@@H@Z)
RVA_COMPGEN(0x0004a260, 0x47, ?ConstructElements@@YGXPAPAVCStringArray@@H@Z)
RVA_COMPGEN(0x0004a2b0, 0x8, ??2@YAPAXIPAX@Z)
RVA_COMPGEN(0x0004a2c0, 0x3b, ?SerializeElements@@YGXAAVCArchive@@PAPAVCStringArray@@H@Z)
RVA_COMPGEN(0x0004a300, 0x21a, ?SetSize@?$CArray@PAVCStringTriple@@PAV1@@@QAEXHH@Z)
RVA_COMPGEN(0x0004a580, 0x24, ?DestructElements@@YGXPAPAVCStringTriple@@H@Z)
RVA_COMPGEN(0x0004a5b0, 0x3b, ?SerializeElements@@YGXAAVCArchive@@PAPAVCStringTriple@@H@Z)
RVA_COMPGEN(0x0004a670, 0x232, ?SetSize@?$CArray@U_WIN32_FIND_DATAA@@U1@@@QAEXHH@Z)
RVA_COMPGEN(0x0004a920, 0x26, ?DestructElements@@YGXPAU_WIN32_FIND_DATAA@@H@Z)
RVA_COMPGEN(0x0004a950, 0x41, ?SerializeElements@@YGXAAVCArchive@@PAU_WIN32_FIND_DATAA@@H@Z)
RVA_COMPGEN(0x0004a9a0, 0x21a, ?SetSize@?$CArray@PAXPAX@@QAEXHH@Z)
RVA_COMPGEN(0x0004abe0, 0x24, ?DestructElements@@YGXPAPAXH@Z)
RVA_COMPGEN(0x0004ac10, 0x3b, ?SerializeElements@@YGXAAVCArchive@@PAPAXH@Z)
RVA_COMPGEN(0x0004ac50, 0x47, ?ConstructElements@@YGXPAPAVCStringTriple@@H@Z)
RVA_COMPGEN(0x0004aca0, 0x50, ?ConstructElements@@YGXPAU_WIN32_FIND_DATAA@@H@Z)
RVA_COMPGEN(0x0004acf0, 0x47, ?ConstructElements@@YGXPAPAXH@Z)

template class CArray<CStringArray*, CStringArray*>;
template class CArray<CStringTriple*, CStringTriple*>;
template class CArray<WIN32_FIND_DATA, WIN32_FIND_DATA>;
template class CArray<void*, void*>;

#include <rva.h>

#include <Serialization/TextureResourceContainers.h>

RVA_COMPGEN(0x000943d0, 0x5a, ?InitHashTable@?$CMap@KAAKVCTextureResourceRecord@@AAV1@@@QAEXIH@Z)
RVA_COMPGEN(0x00094430, 0x84, ?NewAssoc@?$CMap@KAAKVCTextureResourceRecord@@AAV1@@@IAEPAUCAssoc@1@XZ)
RVA_COMPGEN(0x000944c0, 0x36, ?GetAssocAt@?$CMap@KAAKVCTextureResourceRecord@@AAV1@@@IBEPAUCAssoc@1@AAKAAI@Z)
RVA_COMPGEN(0x00094520, 0x55, ??0CTextureResourceRecord@@QAE@XZ)
RVA_COMPGEN(0x00094580, 0x72, ??1CTextureResourceRecord@@QAE@XZ)

RVA_COMPGEN(0x00098aa0, 0x1a6, ?Serialize@?$CArray@UCTextureCommandRecord@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00098cd0, 0x1aa, ?Serialize@?$CArray@UCTextureSpanRecord@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00098ee0, 0x188, ?Serialize@?$CArray@UCTextureRuntimeObjectReference@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x000990d0, 0x23b, ?Serialize@?$CArray@VCTextureDescriptorRecord@@AAV1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00099370, 0x24b, ?Serialize@?$CArray@VCTextureTableRecord@@AAV1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00099620, 0x1a6, ?Serialize@?$CArray@UCTextureBlockRecord@@AAU1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x000998c0, 0x20a, ?Serialize@?$CMap@KAAKVCTextureResourceRecord@@AAV1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00099c20, 0x1eb, ?Serialize@?$CMap@KAAKVCTextureLookupRecord@@AAV1@@@UAEXAAVCArchive@@@Z)
RVA_COMPGEN(0x00099f70, 0x5a, ?InitHashTable@?$CMap@KAAKVCTextureLookupRecord@@AAV1@@@QAEXIH@Z)
RVA_COMPGEN(0x00099fd0, 0x6c, ?NewAssoc@?$CMap@KAAKVCTextureLookupRecord@@AAV1@@@IAEPAUCAssoc@1@XZ)

RVA(0x0009a040, 0x1d)
CTextureTableRecord::CTextureTableRecord() {
    m_tail[0] = 0;
    m_tail[1] = 0;
    m_tail[2] = 0;
    m_tail[3] = 0;
}

RVA_COMPGEN(0x0009a060, 0x1e, ??1CTextureLookupRecord@@QAE@XZ)

void InstantiateTextureResourceContainers(CArchive& archive) {
    CTextureCommandArray commands;
    CTextureSpanArray spans;
    CTextureRuntimeObjectArray objects;
    CTextureDescriptorArray descriptors;
    CTextureTableArray tables;
    CTextureBlockArray blocks;
    CTextureResourceMap resources;
    CTextureLookupMap lookups;

    commands.Serialize(archive);
    spans.Serialize(archive);
    objects.Serialize(archive);
    descriptors.Serialize(archive);
    tables.Serialize(archive);
    blocks.Serialize(archive);
    resources.Serialize(archive);
    lookups.Serialize(archive);
}

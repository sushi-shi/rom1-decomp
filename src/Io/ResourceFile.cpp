#include <rva.h>

#include <Io/ResourceFile.h>

#include <string.h>

RVA(0x000c9d80, 0x4f)
void CResourceManager::Release(CObject* resource) {
    for (i32 index = 0; index < m_count; ++index) {
        if (m_resources[index] == resource) {
            delete resource;
            i32 moveCount = m_count - index - 1;
            CObject** destination = &m_resources[index];
            if (moveCount != 0) {
                memcpy(destination, destination + 1, moveCount * sizeof(CObject*));
            }
            --m_count;
            return;
        }
    }
}

RVA(0x000c9dd0, 0x19)
CResourceFile::CResourceFile() {
    m_resource = 0;
}

RVA(0x000c9e80, 0x4f)
CResourceFile::~CResourceFile() {
    Close();
}

RVA(0x000ca1d0, 0x1a)
void CResourceFile::Close() {
    g_resourceManager.Release(m_resource);
    m_resource = 0;
}

DATA(0x001f2098)
CResourceManager g_resourceManager;

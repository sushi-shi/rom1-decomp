#include <rva.h>

#include <Io/ResourceFile.h>

#include <Bute/ButeMgr.h>

#include <ctype.h>
#include <stdio.h>
#include <string.h>

RVA(0x000c99f0, 0xaf)
void ReadUpdateList(const char* filename) {
    FILE* file = fopen(filename, DATA_COMPGEN(0x001c1ce0, "r"));
    if (file != 0) {
        char line[256];
        while (fgets(line, 255, file) != 0 && isprint(line[0])) {
            char* end = strchr(line, '\n');
            if (end != 0) {
                *end = 0;
            }
            end = strchr(line, '\r');
            if (end != 0) {
                *end = 0;
            }
            g_resourceManager.DisableResource(line);
        }
        fclose(file);
    }
}

RVA(0x000c9aa0, 0x3d)
void CResourceManager::DisableResource(char* path) {
    for (i32 index = 0; index < m_archiveCount; ++index) {
        u32* record = static_cast<u32*>(m_archives[index]->FindResourceRecord(path));
        if (record != 0) {
            record[3] |= RESOURCE_RECORD_DISABLED;
            return;
        }
    }
}

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

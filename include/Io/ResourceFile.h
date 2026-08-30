#ifndef ROM1_IO_RESOURCEFILE_H
#define ROM1_IO_RESOURCEFILE_H

#include <Mfc.h>

#include <Enums.h>
#include <Ints.h>

class CButeMgr;

GZ_ENUM_CONST_BEGIN(ResourceRecordFlags)
    RESOURCE_RECORD_DISABLED = 0x20000000,
GZ_ENUM_CONST_END(ResourceRecordFlags)

// Global owner of mounted archive indices, filesystem search paths, and the
// resource objects referenced by open CResourceFile views. The three array
// layouts are exact; the original game-owned class name has not survived.
class CResourceManager {
public:
    void Release(CObject* resource);
    void DisableResource(char* path);

private:
    // Three executable-proven 20-byte array layouts. Their retail vtables are
    // game-owned (not the MFC CPtrArray/CStringArray identities), so retain
    // the fields without applying incorrect library class names.
    void* m_archiveArrayVtable;
    CButeMgr** m_archives;
    i32 m_archiveCount;
    i32 m_archiveCapacity;
    i32 m_archiveGrowBy;
    BYTE m_searchPaths[0x14];
    void* m_resourceArrayVtable;
    CObject** m_resources;
    i32 m_count;
    i32 m_capacity;
    i32 m_growBy;
};

extern CResourceManager g_resourceManager;
void ReadUpdateList(const char* filename);

// Resource-backed CFile view used throughout the engine. The 32-byte layout
// comes from the retail vtable and direct field accesses. Its original
// game-owned class name has not survived, so this neutral name is provisional.
class CResourceFile : public CFile {
public:
    CResourceFile();
    virtual ~CResourceFile();
    virtual void Close();

private:
    CObject* m_resource;
    u32 m_resourceOffset;
    u32 m_resourceLength;
    u32 m_position;
};

#endif // ROM1_IO_RESOURCEFILE_H

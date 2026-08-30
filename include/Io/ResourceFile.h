#ifndef ROM1_IO_RESOURCEFILE_H
#define ROM1_IO_RESOURCEFILE_H

#include <Mfc.h>

#include <Ints.h>

// Global owner of resource objects referenced by open CResourceFile views.
// Only the executable-proven pointer-table tail is named; the leading state
// and original class name have not survived.
class CResourceManager {
public:
    void Release(CObject* resource);

private:
    BYTE m_unknown[0x2c];
    CObject** m_resources;
    i32 m_count;
};

extern CResourceManager g_resourceManager;

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

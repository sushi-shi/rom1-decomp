#ifndef ROM1_SERIALIZATION_REFERENCEWORLD_H
#define ROM1_SERIALIZATION_REFERENCEWORLD_H

#include <rva.h>

#include <MfcNoInline.h>

#include <Enums.h>

#include <afxtempl.h>

class CWorldItem;
class CWorldObjectRegistry;

GZ_ENUM_CONST_BEGIN(ReferenceWorldConstants)
    REFERENCE_WORLD_ITEM_TRANSIENT = 0x08,
    REFERENCE_WORLD_TRAILER = 0xbadface1,
GZ_ENUM_CONST_END(ReferenceWorldConstants)

struct ReferenceWorldLoadState {
    BYTE hasScenario;
    UINT mode;
};

// These game-owned support types have no surviving class names.  Their names
// describe the roles fixed by CReferenceWorld::Serialize and its callers.
class CWorldItemList {};

class CWorldItemCollection {
public:
    BYTE m_reserved00[4];
    CWorldItemList m_items;
};

class CWorldObject {
public:
    BYTE m_reserved00[0x20];
    CWorldItemCollection* m_itemCollection;
    BYTE m_reserved24[4];
    void* m_attachment;
};

typedef CList<CWorldObject*, CWorldObject*> CWorldObjectList;

class CWorldItem {
public:
    BYTE m_reserved00[0x40];
    UINT m_value40;
    UINT m_value44;
    BYTE m_reserved48[4];
    BYTE m_flags4c;
    BYTE m_reserved4d[0x0f];
    UINT m_value5c;
};

class CWorldObjectIterator {
public:
    CWorldObjectIterator();
    CWorldObject* First(CWorldObjectRegistry* registry);
    CWorldObject* Next();

private:
    CWorldObjectRegistry* m_registry;
    void* m_position;

public:
    CWorldObject* m_current;
};

class CWorldItemIterator {
public:
    CWorldItemIterator();
    CWorldItem* First(CWorldItemList* list);
    CWorldItem* Next();

private:
    CWorldItemList* m_list;
    void* m_position;

public:
    CWorldItem* m_current;
};

class CWorldObjectRegistry {
public:
    void Serialize(CArchive& archive);
    CWorldObject* First();
    CWorldObject* Next(CWorldObject* object);
    UINT CountUnattachedObjects();

private:
    CWorldObjectList m_objects;
    BYTE m_reserved1c[8];
};

class CWorldItemManager {
public:
    virtual void Reset() = 0;
    virtual void Activate() = 0;
    void Remove(CWorldItem* item);
};

class CScenarioPrimary {
public:
    CScenarioPrimary();
    void Serialize(CArchive& archive);

private:
    BYTE m_state[0x1c];
};

class CScenarioSecondary {
public:
    CScenarioSecondary();
    virtual void Activate();
    void Serialize(CArchive& archive);

private:
    BYTE m_state[0x1c];
};

class CScenarioTertiary {
public:
    CScenarioTertiary();
    void Serialize(CArchive& archive);

private:
    BYTE m_state[0x1c];
};

class CScenarioQuaternary {
public:
    virtual void Serialize(CArchive& archive) = 0;
    virtual void Activate() = 0;
};

class CScenarioSubsystems {
public:
    CScenarioPrimary* m_primary;
    CScenarioSecondary* m_secondary;
    CScenarioTertiary* m_tertiary;
    CScenarioQuaternary* m_quaternary;
};

class CScenarioResource {
public:
    CScenarioResource(const char* path);
    ~CScenarioResource();

private:
    BYTE m_state[0x32c];
};

// The embedded MFC map serializes a raw WORD key followed by this 52-byte
// value.  No game-owned name survives for the value type.
struct CWorldMapRecord {
    BYTE m_bytes[0x34];
};

typedef CMap<WORD, WORD, CWorldMapRecord, CWorldMapRecord&> CWorldMapRecordMap;

class CWorldMapData {
public:
    CWorldMapData(CScenarioResource* resource, CWorldItemManager* itemManager);
    void LoadTileTable(const char* path, UINT width, UINT height, UINT value);
    void Serialize(CArchive& archive);
    void Activate();

private:
    BYTE m_tileValues[0x500][0x100];
    UINT m_tileTableWidth;
    UINT m_tileTableHeight;
    BYTE m_reserved50008[0x40ac];
    CWorldMapRecordMap m_records;
    BYTE m_reserved540d0[0x50484];
    UINT m_valuea4554;
};

class CWorldRuntime {
public:
    CWorldRuntime(CWorldMapData* mapData, CWorldObjectRegistry* registry);
    void Serialize(CArchive& archive);
    void Activate();

private:
    BYTE m_reserved0000[0x0008];
    BYTE m_block0008[0x0030];
    BYTE m_reserved0038[0x0a10];
    BYTE m_value0a48;
    BYTE m_value0a49;
    BYTE m_reserved0a4a[0x0002];
    DWORD m_value0a4c;
    BYTE m_reserved0a50[0x9dd8];
    BYTE m_blocka828[0x0190];
    BYTE m_reserveda9b8[0x0004];
    BYTE m_blocka9bc[0x09cc];
    BYTE m_reservedb388[0x0024];
    UINT m_valueb3ac;
    UINT m_valueb3b0;
    UINT m_valueb3b4;
    BYTE m_reservedb3b8[0x097c];
    BYTE m_blockbd34[0x0190];
    BYTE m_blockbec4[0x03e8];
    BYTE m_reservedc2ac[0x0074];
};

class CScenarioObjectMap {
public:
    void Rebuild(CScenarioResource* resource, BOOL preserveState);

private:
    BYTE m_state[0x3c];
};

class CReferenceSnapshot {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_state[0x190];
};

class CReferenceWorld {
public:
    void Serialize(CArchive& archive);
    void WriteServerStateFile();

    UINT m_value00;
    UINT m_value04;
    BYTE m_reserved08[0x0c];
    CScenarioSubsystems* m_subsystems;
    BYTE m_reserved18[0x10];
    CString m_scenarioName;
    BOOL m_scenarioLoaded;
    BYTE m_reserved30[0x14];
    CScenarioObjectMap m_objectMap;
    UINT m_scenarioPathKind;
    UINT m_mode;
    CMapPtrToPtr m_references;
    BYTE m_reserveda4[0x74];
    CReferenceSnapshot* m_snapshot;
    UINT m_value11c;
    UINT m_reserved120;
    UINT m_value124;
    UINT m_value128;
    UINT m_value12c;
    UINT m_value130;
    UINT m_value134;
    UINT m_value138;
    UINT m_value13c;
    UINT m_value140;
    UINT m_value144;
    UINT m_value148;
    BYTE m_reserved14c[0x24];
    CString m_serverStateLine;
};

extern CReferenceWorld* g_referenceWorld;
extern UINT g_seenTokenIds[0x800];
void ResetSeenTokenIds();

#endif // ROM1_SERIALIZATION_REFERENCEWORLD_H

#ifndef ROM1_SERIALIZATION_ARCHIVEARRAYS_H
#define ROM1_SERIALIZATION_ARCHIVEARRAYS_H

#include <MfcNoInline.h>

#include <afxtempl.h>

// This family is serialized only through MFC collection templates.  Retail
// therefore preserves each complete element size and which collections share
// an element type, but not the original game-owned source names.  Keep one
// canonical declaration for every distinct recovered identity until stronger
// field-use evidence supplies semantic names.
// @identity-TODO: recover the original record names and fields.
struct CSharedCollectionValue {
    BYTE m_bytes[4];
};

struct CLargeCollectionRecord {
    BYTE m_bytes[0x68];
};

struct CNamedCollectionRecord {
    BYTE m_bytes[0x3c];
};

struct CFixedCollectionRecord {
    BYTE m_bytes[0x40];
};

struct CCompactCollectionRecord {
    BYTE m_bytes[0x1c];
};

struct CPrimaryStateRecord {
    BYTE m_bytes[0x30];
};

struct CSecondaryStateRecord {
    BYTE m_bytes[0x30];
};

struct CTertiaryStateRecord {
    BYTE m_bytes[0x1c];
};

struct CCollectionHandle {
    BYTE m_bytes[4];
};

struct CMapValueHandle {
    BYTE m_bytes[4];
};

struct CMapObjectHandle {
    BYTE m_bytes[4];
};

struct CMapRecordHandle {
    BYTE m_bytes[4];
};

struct CSharedMapHandle {
    BYTE m_bytes[4];
};

struct CMapTailHandle {
    BYTE m_bytes[4];
};

struct CMapPayloadHandle {
    BYTE m_bytes[4];
};

struct CDeferredCollectionHandle {
    BYTE m_bytes[4];
};

// Four signed half-words are read and written independently at the recovered
// Outpost element-use sites.  The embedded CArray preserves their eight-byte
// aggregate identity.
struct COutpostPlacementRecord {
    short m_values[4];
};

// The scenario-resource constructor and collection accessors preserve these
// two raw record extents.  No address-bearing evidence retains their original
// source names or internal fields.
struct CScenarioResourceIndexRecord {
    BYTE m_bytes[6];
};

struct CScenarioResourceLargeRecord {
    BYTE m_bytes[0xb8];
};

// Retail construction/destruction and member-use sites prove a 12-byte record
// made from exactly three CStrings.  No surviving runtime-class or
// address-bearing string preserves the record's original source name.
class CStringTriple {
private:
    CString m_first;
    CString m_second;
    CString m_third;
};

typedef CArray<CStringArray*, CStringArray*> CStringArrayPointerArray;
typedef CArray<CStringTriple*, CStringTriple*> CStringTriplePointerArray;
typedef CArray<WIN32_FIND_DATA, WIN32_FIND_DATA> Win32FindDataArray;
// @identity-TODO: element use proves pointers, but the pointee identity and
// complete layout do not survive in the current executable evidence.
typedef CArray<void*, void*> OpaquePointerArray;

class Effect;
class Item;
class Spell;
class SpellEffect;
class VirtualCaster;
class CWorldItem;
class CScenarioBuildingCollection;
class CScenarioBuildingCaster;
class CScenarioBuildingRecord;
class CScenarioUnitRecord;
class CMultiShopInstance;
struct CSpellDefinition;

// The parser allocates 0x1c-byte polymorphic entries and stores their pointers
// in the same list used for the Humans, Outposts, and Items sections.  No
// surviving runtime-class name identifies the pointee more narrowly.
class CParsedScenarioEntry {
private:
    BYTE m_state[0x1c];
};

// The owning constructor families append separately allocated scenario
// objects to this common pointer array.  The pointees have several recovered
// concrete extents, so retain only their proven common pointer identity here.
class CScenarioResourceObject;

struct CScenarioResourceObjectReference {
    CScenarioResourceObject* m_value;
};

// The queue removes pointers and immediately dispatches virtual slot 5 on the
// pointee.  This corrects the earlier size-only four-byte placeholder without
// inventing the lost class name.
class CQueuedCollectionObject;

struct CQueuedCollectionReference {
    CQueuedCollectionObject* m_value;
};

// Construction at 0x113d2a and the two owning lists prove a 0x31c-byte,
// non-polymorphic scenario-resource entry.  Its fields remain separate work.
class CScenarioResourceEntry {
private:
    BYTE m_state[0x31c];
};

// The four scenario arrays contain distinct pointer domains, but no retained
// symbol identifies the pointee classes.  Preserve the observed pointer word
// and domain separation without inventing complete pointee layouts.
struct CScenarioBuildingCollectionReference {
    CScenarioBuildingCollection* m_value;
};

struct CScenarioBuildingCasterReference {
    CScenarioBuildingCaster* m_value;
};

struct CScenarioBuildingRecordReference {
    CScenarioBuildingRecord* m_value;
};

struct CScenarioUnitRecordReference {
    CScenarioUnitRecord* m_value;
};

typedef CArray<int, int> CSignedIndexArray;
typedef CArray<double, double> CDoubleArray;
typedef CArray<CLargeCollectionRecord, CLargeCollectionRecord&> CLargeCollectionRecordArray;
typedef CArray<CNamedCollectionRecord, CNamedCollectionRecord&> CNamedCollectionRecordArray;
typedef CArray<CFixedCollectionRecord, CFixedCollectionRecord&> CFixedCollectionRecordArray;
typedef CArray<CCompactCollectionRecord, CCompactCollectionRecord&> CCompactCollectionRecordArray;
typedef CArray<CPrimaryStateRecord, CPrimaryStateRecord&> CPrimaryStateRecordArray;
typedef CArray<CSecondaryStateRecord, CSecondaryStateRecord&> CSecondaryStateRecordArray;
typedef CArray<CTertiaryStateRecord, CTertiaryStateRecord&> CTertiaryStateRecordArray;
typedef CArray<CSpellDefinition, CSpellDefinition&> CSpellDefinitionRecordArray;
typedef CArray<Spell*, Spell*> CSpellPointerArray;
typedef CArray<COutpostPlacementRecord, COutpostPlacementRecord&> COutpostPlacementRecordArray;
typedef CArray<CScenarioResourceIndexRecord, CScenarioResourceIndexRecord&>
    CScenarioResourceIndexRecordArray;
typedef CArray<CScenarioResourceLargeRecord, CScenarioResourceLargeRecord&>
    CScenarioResourceLargeRecordArray;
typedef CArray<CScenarioBuildingCollectionReference, CScenarioBuildingCollectionReference&>
    CScenarioBuildingCollectionPointerArray;
typedef CArray<CScenarioBuildingCasterReference, CScenarioBuildingCasterReference&>
    CScenarioBuildingCasterPointerArray;
typedef CArray<CScenarioBuildingRecordReference, CScenarioBuildingRecordReference&>
    CScenarioBuildingRecordPointerArray;
typedef CArray<CScenarioUnitRecordReference, CScenarioUnitRecordReference&>
    CScenarioUnitRecordPointerArray;
typedef CArray<CMultiShopInstance*, CMultiShopInstance*> CMultiShopInstancePointerArray;

#endif // ROM1_SERIALIZATION_ARCHIVEARRAYS_H

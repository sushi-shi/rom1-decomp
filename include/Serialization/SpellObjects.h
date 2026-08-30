#ifndef ROM1_SERIALIZATION_SPELLOBJECTS_H
#define ROM1_SERIALIZATION_SPELLOBJECTS_H

#include <rva.h>

#include <MfcNoInline.h>

#include <Serialization/ArchiveArrays.h>
#include <Serialization/ReferenceWorld.h>

#include <afxtempl.h>

class Spell;
class Spellbook;
class SpellEffect;
class PointEffect;
class AreaEffect;
class Effect;
class VirtualCaster;
class Unit;
class Humanoid;
class Diary;
class Human;
class Player;
class Item;
class CUnitRawArchiveRecord;
class CWordListRecordLarge;
class CWordListRecordCompact;
class CPlayerArchiveBlock;
class CPlayerUnitGroup;
class CPlayerUnitGroupCollection;

void ResolveEffectReference(UINT* value);
void ResolveTokenReference(UINT* value);
void ResolvePlayerReference(UINT* value);
UINT TransformPlayerReference(UINT value);

// The pointed-to object at Token+0x10 serializes exactly twelve raw bytes.
// Its original type name has not survived, so retain a layout-only name.
class CTokenPayload {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_bytes[12];
};

class CDirectDamagePayload {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_bytes[24];
};

// These embedded records are copied as raw bytes by their only recovered
// methods. Their original source names and field semantics do not survive.
class CUnitArchiveBlock {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_bytes[0x40];
};

class CSharedArchiveBlock {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_bytes[0x16];
};

typedef CArray<CSpellDefinition, CSpellDefinition&> CSpellDefinitionArray;

// The three equipment tables and the base-item table are alternate uses of
// the same TableLine-derived array identities recovered from Data.bin.
typedef CNamedCollectionRecordArray CEquipmentDefinitionArray;
typedef CFixedCollectionRecordArray CItemDefinitionArray;

// The Data.bin load/save wrappers and the .csv bootstrap path prove this
// complete non-polymorphic owner layout.  The executable retains the table
// roles and element extents but not the original owner identifier, so keep a
// role name rather than inventing a historical class name.  Element zero is
// a live entry only for the material/shape/magic tables; the remaining
// definition arrays retain their one-based indexing from the retail loops.
class CStaticDataTables {
public:
    void Serialize(CArchive& archive);

private:
    CLargeCollectionRecordArray m_materials;
    CLargeCollectionRecordArray m_shapes;
    CNamedCollectionRecordArray m_shields;
    CNamedCollectionRecordArray m_armors;
    CNamedCollectionRecordArray m_weapons;
    CFixedCollectionRecordArray m_magicItems;
    CCompactCollectionRecordArray m_magic;
    CPrimaryStateRecordArray m_units;
    CSecondaryStateRecordArray m_humans;
    CSecondaryStateRecordArray m_auxiliaryStates;
    CTertiaryStateRecordArray m_buildings;
    CSpellDefinitionRecordArray m_spells;
    BOOL m_loaded;
};

// Typed archive readers prove the element identities for both four-byte list
// instantiations in the retail container band.
typedef CList<Effect*, Effect*> CEffectPointerList;
typedef CList<Item*, Item*> CItemPointerList;

// The game-owned pointer-list wrapper is a template: the Effect* and Item*
// instantiations have identical storage, control flow, and paired compiler
// helper emissions in retail.  Its original identifier has not survived.
template<class TYPE> class CArchivePointerList {
public:
    void Serialize(CArchive& archive);

private:
    CList<TYPE, TYPE> m_items;
};

typedef CArchivePointerList<Effect*> CEffectArchiveList;
typedef CArchivePointerList<Item*> CItemArchiveList;

// Unit owns this separately allocated extension of the item archive list.
// Its constructor and serializer fix the 0x24-byte allocation and trailing
// two DWORDs; no original class name survives.
class CUnitItemList {
public:
    void Serialize(CArchive& archive);

private:
    CItemArchiveList m_items;
    UINT m_value1c;
    UINT m_value20;
};

class Token : public CObject {
public:
    static AFX_DATA CRuntimeClass classToken;
    virtual void Serialize(CArchive& archive);

    // Token's retail vtable introduces slots 5-13.  Their semantic names and
    // all but slot 12's return type remain unidentified; retain neutral names
    // so calls through the proven slot keep the recovered class shape.
    virtual void TokenVirtual05();
    virtual void TokenVirtual06();
    virtual void TokenVirtual07();
    virtual void TokenVirtual08();
    virtual void TokenVirtual09();
    virtual void TokenVirtual10();
    virtual void TokenVirtual11();
    virtual BOOL TokenVirtual12();
    virtual void TokenVirtual13();

    friend CArchive& AFXAPI operator>>(CArchive& archive, Token*& value);

protected:
    UINT m_value04;
    UINT m_value08;
    BYTE m_value0c;
    BYTE m_reserved0d;
    WORD m_value0e;
    CTokenPayload* m_payload;
    UINT m_reference14;
    WORD m_value18;
    WORD m_reserved1a;
    UINT m_value1c;
    CEffectArchiveList m_effects;
};

// Runtime-class records prove these inheritance edges and complete sizes.
// Opaque tails preserve only that executable evidence until their individual
// serializers and methods recover the fields.
class VirtualCaster : public Token {
public:
    static AFX_DATA CRuntimeClass classVirtualCaster;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, VirtualCaster*& value);

private:
    BYTE m_value3c;
    BYTE m_reserved3d[3];
    BYTE* m_values40;
};

// Runtime-class record 0x1c3360 fixes Token as the base and the complete
// 0x50-byte size. The fields beyond Token remain unrecovered.
class Item : public Token {
public:
    static AFX_DATA CRuntimeClass classItem;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Item*& value);

protected:
    void* m_definition3c;
    WORD m_value40;
    WORD m_value42;
    BYTE m_value44;
    BYTE m_value45;
    BYTE m_value46;
    BYTE m_value47;
    short m_value48;
    short m_value4a;
    BYTE m_reserved4c[4];
};

class Unit : public Token {
public:
    static AFX_DATA CRuntimeClass classUnit;
    virtual void Serialize(CArchive& archive);
    virtual BOOL TokenVirtual12();

    friend CArchive& AFXAPI operator>>(CArchive& archive, Unit*& value);
    friend class CPlayerUnitGroup;

protected:
    TableLine* m_state3c;
    UINT m_reference40;
    UINT m_reference44;
    char m_value48;
    BYTE m_values49[4];
    BYTE m_reserved4d[3];
    BYTE m_raw50[4];
    BYTE m_raw54[4];
    BYTE m_raw58[4];
    UINT m_reference5c;
    BYTE m_value60;
    BYTE m_value61;
    BYTE m_reserved62[2];
    UINT m_reference64;
    Item* m_item68;
    char m_value6c;
    BYTE m_reserved6d[3];
    CPlayerUnitGroup* m_group70;
    Item* m_item74;
    Item* m_item78;
    CUnitItemList* m_itemList7c;
    CString m_value80;
    short m_value84;
    short m_value86;
    short m_value88;
    short m_value8a;
    short m_value8c;
    short m_value8e;
    short m_value90;
    short m_value92;
    short m_value94;
    short m_value96;
    short m_value98;
    short m_value9a;
    short m_value9c;
    short m_value9e;
    short m_valuea0;
    BYTE m_valuea2;
    BYTE m_valuea3;
    WORD m_valuea4;
    CDirectDamagePayload m_damagea6;
    CSharedArchiveBlock m_sharedbe;
    CUnitArchiveBlock m_blockd4;
    CDirectDamagePayload m_damage114;
    BYTE m_value12c;
    BYTE m_reserved12d[3];
    UINT m_value130;
    BYTE m_value134;
    BYTE m_value135;
    BYTE m_value136;
    BYTE m_reserved137;
    UINT m_value138;
    BYTE m_value13c;
    BYTE m_reserved13d[3];
    Spellbook* m_spellbook140;
    UINT m_value144;
    UINT m_value148;
    BYTE m_value14c;
    BYTE m_reserved14d[3];
    UINT m_value150;
    CUnitRawArchiveRecord* m_raw154;
    CWordListRecordLarge* m_words158;
    CList<WORD, WORD> m_words15c;
    CList<WORD, WORD> m_words178;
    UINT m_value194;
};

class Humanoid : public Unit {
public:
    static AFX_DATA CRuntimeClass classHumanoid;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Humanoid*& value);

protected:
    Item* m_items198[13];
    BYTE m_values1cc[0x18];
    Diary* m_diary1e4;
};

class Diary : public CObject {
public:
    static AFX_DATA CRuntimeClass classDiary;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Diary*& value);

private:
    CObArray m_entries04;
    CObArray m_entries18;
    UINT m_reference2c;
};

class Human : public Humanoid {
public:
    static AFX_DATA CRuntimeClass classHuman;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Human*& value);
};

class Player : public CObject {
public:
    static AFX_DATA CRuntimeClass classPlayer;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Player*& value);

private:
    short m_value04;
    WORD m_reserved06;
    UINT m_value08;
    BYTE m_reserved0c[4];
    BYTE m_raw10[8];
    CString m_name18;
    UINT m_value1c;
    CWorldItemManager* m_itemManager20;
    CPlayerUnitGroupCollection* m_groups24;
    UINT m_value28;
    WORD m_value2c;
    WORD m_reserved2e;
    CPlayerArchiveBlock* m_archive30;
    UINT m_reference34;
    UINT m_reference38;
    BYTE m_value3c;
    BYTE m_value3d;
    WORD m_reserved3e;
    CObject* m_object40;
    BYTE m_value44;
    BYTE m_reserved45[3];
    UINT m_reference48;
    int m_value4c;
    UINT m_value50;
    int m_value54;
    UINT m_value58;
    BYTE m_reserved5c[0x14];
};

// A Player group begins with the Unit* list consumed through the recovered
// world-list iterator, followed by its archive identity, WORD list, compact
// state record, and two recovered references. Construction and Add/Remove
// sites prove the back-pointer at Unit+0x70 and the complete 0x48-byte extent.
class CPlayerUnitGroup : public CWorldItemList {
public:
    CPlayerUnitGroup();
    void Serialize(CArchive& archive);
    void AddUnit(Unit* unit);
    void RemoveUnit(Unit* unit);

private:
    CList<Unit*, Unit*> m_units;
    UINT m_reference1c;
    CList<WORD, WORD> m_values20;
    CWordListRecordCompact* m_archive3c;
    UINT m_reference40;
    UINT m_reference44;
};

// Player+0x24 owns this separately allocated collection. The serializer,
// count/add wrappers, and iterator helpers prove a CList of group pointers.
class CPlayerUnitGroupCollection {
public:
    void Serialize(CArchive& archive);

private:
    int GetCount() const;
    void Add(CPlayerUnitGroup* group);

    CList<CPlayerUnitGroup*, CPlayerUnitGroup*> m_groups;

    friend class CPlayerUnitGroupIterator;
};

// The two-word iterator shape and its First/Next call sites are exact. The
// collection's element identity is a CWorldItemList consumed immediately by
// the already recovered CWorldItemIterator.
class CPlayerUnitGroupIterator {
public:
    CPlayerUnitGroupIterator();
    CWorldItemList* First(CPlayerUnitGroupCollection* groups);
    CWorldItemList* Next();

private:
    const CPlayerUnitGroupCollection* m_groups;
    POSITION m_position;
};

class SpellEffect : public Token {
public:
    static AFX_DATA CRuntimeClass classSpellEffect;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, SpellEffect*& value);

protected:
    UINT m_reserved3c;
    BYTE m_value40;
    BYTE m_value41;
    WORD m_reserved42;
};

class SpellTransport : public SpellEffect {
public:
    static AFX_DATA CRuntimeClass classSpellTransport;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, SpellTransport*& value);

private:
    SpellEffect* m_effect44;
    AreaEffect* m_area48;
    short m_value4c;
    WORD m_reserved4e;
};

class PointEffect : public SpellEffect {
public:
    static AFX_DATA CRuntimeClass classPointEffect;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, PointEffect*& value);

private:
    UINT m_reference44;
    Effect* m_effect48;
};

class AreaEffect : public SpellEffect {
public:
    static AFX_DATA CRuntimeClass classAreaEffect;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, AreaEffect*& value);

private:
    Effect* m_effect44;
    BYTE m_values48[4];
    WORD m_value4c;
    WORD m_reserved4e;
};

class Effect : public Token {
public:
    static AFX_DATA CRuntimeClass classEffect;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Effect*& value);

protected:
    BYTE m_value3c;
    BYTE m_value3d;
    WORD m_reserved3e;
    UINT m_value40;
    UINT m_reserved44;
};

class Effect_DirectDamage : public Effect {
public:
    static AFX_DATA CRuntimeClass classEffect_DirectDamage;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Effect_DirectDamage*& value);

private:
    CDirectDamagePayload m_damage;
};

// Runtime-class records prove this complete game-object hierarchy and every
// complete size. The field identities have not survived, so keep the newly
// introduced tails opaque until their individual methods recover them.
class Building : public Token {
public:
    static AFX_DATA CRuntimeClass classBuilding;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Building*& value);

protected:
    CTertiaryStateRecord* m_definition;
    BYTE m_value40;
    BYTE m_reserved41;
    short m_value42;
    short m_value44;
    short m_value46;
    BYTE m_value48;
    BYTE m_reserved49;
    CSharedArchiveBlock m_values4a;
    BYTE m_value60;
    BYTE m_value61;
    WORD m_reserved62;
    DWORD m_value64;
    DWORD m_value68;
};

class Outpost : public Building {
public:
    static AFX_DATA CRuntimeClass classOutpost;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Outpost*& value);

private:
    COutpostPlacementRecordArray m_placements;
    UINT m_value80;
    UINT m_value84;
    UINT m_value88;
    UINT m_value8c;
    BYTE m_state90[0x1c];
};

class Tavern : public Building {
public:
    static AFX_DATA CRuntimeClass classTavern;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Tavern*& value);

private:
    BYTE m_reserved6c[0x30];
    UINT m_value9c;
};

class Shop : public Building {
public:
    static AFX_DATA CRuntimeClass classShop;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Shop*& value);

private:
    UINT m_reserved6c;
    UINT m_value70;
};

class CMultiShopShelf : public CObject {
public:
    static AFX_DATA CRuntimeClass classCMultiShopShelf;

    friend CArchive& AFXAPI operator>>(CArchive& archive, CMultiShopShelf*& value);

private:
    BYTE m_state04[0x18];
};

class CMultiShopInstance : public CObject {
public:
    static AFX_DATA CRuntimeClass classCMultiShopInstance;

    friend CArchive& AFXAPI operator>>(CArchive& archive, CMultiShopInstance*& value);

private:
    BYTE m_state04[0x9c];
};

class CMultiShopTemplate : public CObject {
public:
    static AFX_DATA CRuntimeClass classCMultiShopTemplate;

    friend CArchive& AFXAPI operator>>(CArchive& archive, CMultiShopTemplate*& value);

private:
    BYTE m_state04[0x78];
    CMultiShopInstancePointerArray m_instances;
    UINT m_value90;
    UINT m_value94;
};

class Armor : public Item {
public:
    static AFX_DATA CRuntimeClass classArmor;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Armor*& value);

private:
    BYTE m_value50;
    BYTE m_reserved51;
    CSharedArchiveBlock m_shared52;
};

class Shield : public Item {
public:
    static AFX_DATA CRuntimeClass classShield;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Shield*& value);

private:
    CSharedArchiveBlock m_shared50;
    WORD m_reserved66;
};

class Weapon : public Item {
public:
    static AFX_DATA CRuntimeClass classWeapon;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Weapon*& value);

private:
    BYTE m_value50;
    BYTE m_reserved51;
    CDirectDamagePayload m_damage52;
    CSharedArchiveBlock m_shared6a;
    Spell* m_spell80;
};

class Sack : public Token {
public:
    static AFX_DATA CRuntimeClass classSack;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Sack*& value);

private:
    UINT m_value3c;
    CUnitItemList* m_itemList40;
};

class Spell : public CObject {
public:
    static AFX_DATA CRuntimeClass classSpell;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Spell*& value);

private:
    void* m_definition;
    BYTE m_values08[3];
    BYTE m_reserved0b;
    short m_value0c;
    BYTE m_reserved0e[6];
};

class Spellbook : public CObject {
public:
    static AFX_DATA CRuntimeClass classSpellbook;
    Spellbook();
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Spellbook*& value);

private:
    CArray<Spell*, Spell*> m_spells;
    UINT m_value18;
};

template<class TYPE> void CArchivePointerList<TYPE>::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        POSITION position = m_items.GetHeadPosition();
        archive << static_cast<UINT>(m_items.GetCount());
        while (position != 0) {
            TYPE value = m_items.GetNext(position);
            archive << value;
        }
    } else {
        m_items.RemoveAll();
        UINT count;
        archive >> count;
        for (int i = 0; i < static_cast<int>(count); i++) {
            TYPE value = 0;
            archive >> value;
            m_items.AddTail(value);
        }
    }
}

#endif // ROM1_SERIALIZATION_SPELLOBJECTS_H

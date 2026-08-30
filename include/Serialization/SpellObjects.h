#ifndef ROM1_SERIALIZATION_SPELLOBJECTS_H
#define ROM1_SERIALIZATION_SPELLOBJECTS_H

#include <rva.h>

#include <MfcNoInline.h>

#include <Serialization/ReferenceWorld.h>

#include <afxtempl.h>

class Spell;
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
struct CTertiaryStateRecord;

void ResolveEffectReference(UINT* value);
void ResolveTokenReference(UINT* value);

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

// The element stride and CArray accessors prove a contiguous 32-byte spell
// definition record. Its original record name and fields remain unknown.
struct CSpellDefinition {
    BYTE m_bytes[0x20];
};

typedef CArray<CSpellDefinition, CSpellDefinition&> CSpellDefinitionArray;
// Typed archive readers prove the element identities for both four-byte list
// instantiations in the retail container band.
typedef CList<Effect*, Effect*> CEffectPointerList;
typedef CList<Item*, Item*> CItemPointerList;

class Token : public CObject {
public:
    static AFX_DATA CRuntimeClass classToken;
    virtual void Serialize(CArchive& archive);

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
    CEffectPointerList m_effects;
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
    BYTE m_state3c[0x08];
};

// Runtime-class record 0x1c3360 fixes Token as the base and the complete
// 0x50-byte size. The fields beyond Token remain unrecovered.
class Item : public Token {
public:
    static AFX_DATA CRuntimeClass classItem;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Item*& value);

protected:
    BYTE m_state3c[0x14];
};

class Unit : public Token {
public:
    static AFX_DATA CRuntimeClass classUnit;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Unit*& value);

protected:
    BYTE m_state3c[0x15c];
};

class Humanoid : public Unit {
public:
    static AFX_DATA CRuntimeClass classHumanoid;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Humanoid*& value);

protected:
    BYTE m_state198[0x50];
};

class Diary : public CObject {
public:
    static AFX_DATA CRuntimeClass classDiary;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Diary*& value);

private:
    BYTE m_state04[0x2c];
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
    BYTE m_state04[0x6c];
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
    BYTE m_state6c[0x40];
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
    BYTE m_state04[0x94];
};

class Armor : public Item {
public:
    static AFX_DATA CRuntimeClass classArmor;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Armor*& value);

private:
    BYTE m_state50[0x18];
};

class Shield : public Item {
public:
    static AFX_DATA CRuntimeClass classShield;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Shield*& value);

private:
    BYTE m_state50[0x18];
};

class Weapon : public Item {
public:
    static AFX_DATA CRuntimeClass classWeapon;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Weapon*& value);

private:
    BYTE m_state50[0x34];
};

class Sack : public Token {
public:
    static AFX_DATA CRuntimeClass classSack;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Sack*& value);

private:
    BYTE m_state3c[0x08];
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
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, Spellbook*& value);

private:
    CArray<Spell*, Spell*> m_spells;
    UINT m_value18;
};

#endif // ROM1_SERIALIZATION_SPELLOBJECTS_H

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

class Token : public CObject {
public:
    static AFX_DATA CRuntimeClass classToken;
    virtual void Serialize(CArchive& archive);

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
    BYTE m_reserved20[0x1c];
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

private:
    CDirectDamagePayload m_damage;
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

private:
    CArray<Spell*, Spell*> m_spells;
    UINT m_value18;
};

#endif // ROM1_SERIALIZATION_SPELLOBJECTS_H

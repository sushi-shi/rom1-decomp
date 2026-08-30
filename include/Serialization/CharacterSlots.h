#ifndef ROM1_SERIALIZATION_CHARACTERSLOTS_H
#define ROM1_SERIALIZATION_CHARACTERSLOTS_H

#include <MfcWin.h>

#include <Enums.h>
#include <Ints.h>

#include <afxtempl.h>

GZ_ENUM_CONST_BEGIN(CharacterSlotConstants)
    CHARACTER_SLOT_GAME_MODE = 2,
GZ_ENUM_CONST_END(CharacterSlotConstants)

union CRegistryPathBuffer {
    char characters[0x100];
    BYTE bytes[0x100];
};

class CUnitDetail : public CObject {
public:
    CUnitDetail();
    virtual ~CUnitDetail();
    void Write(CFile* file);
    void Read(CFile* file);

private:
    WORD m_value04;
    BYTE m_serialized06[5];
    BYTE m_reserved0b;
    BYTE* m_data;
    DWORD m_value10;
    DWORD m_value14;
    DWORD m_value18;
    i32 m_value1c;
    i32 m_value20;
};

class CUnit : public CObject {
public:
    CUnit();

    virtual void CUnitVirtual05();
    virtual void CUnitVirtual06();
    virtual void CUnitVirtual07();
    virtual void CUnitVirtual08();
    virtual void CUnitVirtual09();
    virtual void CUnitVirtual10();
    virtual void CUnitVirtual11();
    virtual void CUnitVirtual12();
    virtual void CUnitVirtual13();
    virtual void CUnitVirtual14();
    virtual void CUnitVirtual15();
    virtual void CUnitVirtual16();
    virtual void CUnitVirtual17();
    virtual void CUnitVirtual18();
    virtual void CUnitVirtual19();
    virtual void CUnitVirtual20();
    virtual void Initialize(
        i32 value1,
        i32 value2,
        i32 value3,
        i32 value4,
        i32 value5,
        i32 definition,
        i32 value7,
        i32 value8,
        i32 value9,
        i32 value10
    );
    virtual void CUnitVirtual22();
    virtual void CUnitVirtual23();
    virtual void CUnitVirtual24();
    virtual void CUnitVirtual25();
    virtual void CUnitVirtual26();
    virtual void CUnitVirtual27();
    virtual void CUnitVirtual28();
    virtual void CUnitVirtual29();
    virtual void CUnitVirtual30();
    virtual void CUnitVirtual31();
    virtual void CUnitVirtual32();

    void FinishLoading();

    BYTE m_reserved04[0x1c];
    DWORD m_value20;
    DWORD m_value24;
    BYTE m_reserved28[0x84];
    BYTE m_dataac[0x20];
    BYTE m_reservedcc[0x18];
    BYTE m_datae4[0x28];
    BYTE m_reserved10c[0x2c];
    BYTE m_data138[0x20];
    BYTE m_reserved158[4];
    CUnitDetail* m_details[12];
    DWORD m_characterMode;
    BYTE m_reserved190[0x20];
};

class CUnitDefinitionTable {
public:
    DWORD m_defaultDefinition;
};

typedef CMap<WORD, WORD, CUnit*, CUnit*> CUnitMap;

class CGameWorldState {
public:
    virtual void WorldVirtual00();
    virtual void WorldVirtual01();
    virtual void WorldVirtual02();
    virtual void WorldVirtual03();
    virtual void WorldVirtual04();
    virtual void WorldVirtual05();
    virtual void WorldVirtual06();
    virtual void WorldVirtual07();
    virtual void WorldVirtual08();
    virtual void WorldVirtual09();
    virtual void WorldVirtual10();
    virtual void WorldVirtual11();
    virtual void WorldVirtual12();
    virtual void WorldVirtual13();
    virtual void WorldVirtual14();
    virtual void WorldVirtual15();
    virtual void WorldVirtual16();
    virtual void WorldVirtual17();
    virtual void Notify(UINT message, UINT value1, UINT value2);

    BYTE m_reserved004[0x9a0];
    CUnitDefinitionTable* m_unitDefinitions;
    BYTE m_reserved9a8[0x10];
    CUnitMap m_units;
    BYTE m_reserved9d4[0x3580];
    CUnit* m_currentUnit;
};

class CCharacterStatistics {
public:
    BYTE m_reserved00[0x64];
    i32 m_values[4];
};

class CGameConfiguration {
public:
    char m_globalMapPath[0x20];
    DWORD m_values20[0x5c];
    const char* m_registryKey;
};

union CCharacterSlotData {
    BYTE bytes[0x54];
    struct {
        DWORD values[4];
        DWORD reserved10;
        DWORD packedStatistics;
        BYTE reserved18[0x14];
        DWORD unitValue;
        BYTE reserved30[0x24];
    } fields;
};

// Embedded at CMainWindow+0x420.  The original class name is not present in
// retail symbols, so this semantic name records its observed responsibility:
// indexing, loading, and updating the gameNNNN.chr character slots.
class CCharacterSlots : public CObject {
public:
    CString CharacterFileName(i32 fileIndex);
    void RefreshCharacters();
    void DeleteTemporaryCharacters();
    void LoadCharacter(i32 index);
    void RenameCurrentCharacter(const char* name);
    void SaveCharacter(CWordArray* words);
    void RebuildCharacterDetails();

private:
    u8 m_reserved04[4];
    BYTE m_header08[8];
    char m_characterName[0x20];
    char m_secondaryName[0x20];
    BYTE m_reserved50[0x20];
    DWORD m_characterFlags;
    DWORD m_characterFlags2;
    CCharacterSlotData m_characterData;
    CStringArray m_characterNames;
    DWORD m_reservedFileArrayGap;
    CDWordArray m_characterFileIds;
    CDWordArray m_reservedFileIds;
    i32 m_currentIndex;
    CWordArray m_words;
};

class CCharacterSaveWarning : public CDialog {
public:
    CCharacterSaveWarning(
        i32 style,
        i32 x,
        i32 y,
        i32 width,
        i32 height,
        const char* text,
        i32 value1,
        i32 value2
    );

private:
    BYTE m_reserved5c[0x1c];
};

class CMainWindow : public CFrameWnd {
public:
    void ShowCharacterWarning(CCharacterSaveWarning* warning);

    BYTE m_reserved0bc[0x14];
    CGameWorldState* m_world;
    BYTE m_reservedd4[0x18];
    CCharacterStatistics* m_characterStatistics;
    BYTE m_reservedf0[0x2c8];
    DWORD m_characterRevision;
    BYTE m_reserved3bc[0x64];
    CCharacterSlots m_characterSlots;
    BYTE m_reserved544[0x178];
    i32 m_gameMode;
};

#endif // ROM1_SERIALIZATION_CHARACTERSLOTS_H

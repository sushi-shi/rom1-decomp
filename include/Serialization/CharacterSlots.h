#ifndef ROM1_SERIALIZATION_CHARACTERSLOTS_H
#define ROM1_SERIALIZATION_CHARACTERSLOTS_H

#include <MfcWin.h>

#include <Ints.h>

// Embedded at CMainWindow+0x420.  The original class name is not present in
// retail symbols, so this semantic name records its observed responsibility:
// indexing, loading, and updating the gameNNNN.chr character slots.
class CCharacterSlots : public CObject {
public:
    CString CharacterFileName(i32 fileIndex);
    void RenameCurrentCharacter(const char* name);

private:
    u8 m_reserved04[0x0c];
    char m_characterName[0x20];
    char m_secondaryName[0x20];
    u8 m_reserved50[0x7c];
    CStringArray m_characterNames;
    CDWordArray m_characterFileIds;
    CDWordArray m_reservedFileIds;
    i32 m_currentIndex;
    CWordArray m_words;
};

#endif // ROM1_SERIALIZATION_CHARACTERSLOTS_H

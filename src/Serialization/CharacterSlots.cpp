#include <rva.h>

#include <Serialization/CharacterSlots.h>

#include <stdio.h>
#include <string.h>

RVA(0x0007a740, 0x48)
CString CCharacterSlots::CharacterFileName(i32 fileIndex) {
    char fileName[0x80];
    sprintf(fileName, "game%04d.chr", fileIndex);
    return CString(fileName);
}

RVA(0x0007b250, 0xe1)
void CCharacterSlots::RenameCurrentCharacter(const char* name) {
    strcpy(m_characterName, name);
    m_characterNames[m_currentIndex] = name;

    CFile file(CharacterFileName(m_characterFileIds[m_currentIndex]), CFile::modeWrite);
    file.Seek(0x0c, CFile::begin);
    file.Write(m_characterName, sizeof(m_characterName));
    file.Close();
}

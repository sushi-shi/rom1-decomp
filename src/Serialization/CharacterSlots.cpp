#include <rva.h>

#include <Serialization/CharacterSlots.h>

#include <Text/ItemNames.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const DWORD CHARACTER_SIGNATURE = 0x68436c41;
static const DWORD CHARACTER_INCOMPLETE = 0x01;
static const DWORD CHARACTER_SPECIAL = 0x04;

typedef CArray<FILETIME, FILETIME&> CFileTimeArray;

RVA(0x0007a740, 0x48)
CString CCharacterSlots::CharacterFileName(i32 fileIndex) {
    char fileName[0x80];
    sprintf(fileName, "game%04d.chr", fileIndex);
    return CString(fileName);
}

RVA(0x0007a800, 0x3a8)
void CCharacterSlots::RefreshCharacters() {
    CDWordArray& characterFileIds = m_characterFileIds;
    characterFileIds.SetSize(0);
    CDWordArray& reservedFileIds = m_reservedFileIds;
    reservedFileIds.SetSize(0);
    CStringArray& characterNames = m_characterNames;
    characterNames.SetSize(0);

    CFileTimeArray writeTimes;
    CFileFind finder;
    CMainWindow* mainWindow = static_cast<CMainWindow*>(AfxGetMainWnd());
    if (mainWindow->m_gameMode != CHARACTER_SLOT_GAME_MODE) {
        if (finder.FindFile("game????.chr")) {
            BOOL more;
            do {
                more = finder.FindNextFile();

                CString fileName = finder.GetFileName();
                fileName = fileName.Mid(4, 4);
                i32 fileIndex;
                sscanf(fileName, "%d", &fileIndex);

                CFile file;
                fileName = finder.GetFileName();
                file.Open(fileName, CFile::modeRead);

                DWORD signature;
                file.Read(&signature, sizeof(signature));
                if (signature == CHARACTER_SIGNATURE) {
                    file.Seek(0x0c, CFile::begin);
                    file.Read(m_characterName, sizeof(m_characterName));
                    file.Seek(0x6c, CFile::begin);

                    DWORD characterRevision;
                    file.Read(&characterRevision, sizeof(characterRevision));
                    if (characterRevision == mainWindow->m_characterRevision) {
                        FILETIME writeTime;
                        finder.GetLastWriteTime(&writeTime);

                        i32 insertIndex = 0;
                        while (insertIndex < writeTimes.GetSize()
                               && CompareFileTime(&writeTime, &writeTimes[insertIndex]) < 1) {
                            ++insertIndex;
                        }
                        writeTimes.InsertAt(insertIndex, writeTime);
                        characterFileIds.InsertAt(insertIndex, fileIndex);
                        characterNames.InsertAt(insertIndex, m_characterName);
                    } else {
                        reservedFileIds.SetAtGrow(reservedFileIds.GetSize(), fileIndex);
                    }
                }
                file.Close();
            } while (more != FALSE);
        }
        finder.Close();
        m_currentIndex = 0;
        LoadCharacter(0);
    }

    characterNames.SetAtGrow(characterNames.GetSize(), static_cast<const char*>(g_textLines[120]));
}

// @dead-code: no retail caller survives for the temporary-slot cleanup pass.
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x0007abc0, 0x1da)
void CCharacterSlots::DeleteTemporaryCharacters() {
    CFileFind finder;
    CMainWindow* mainWindow = static_cast<CMainWindow*>(AfxGetMainWnd());
    if (mainWindow->m_gameMode != CHARACTER_SLOT_GAME_MODE) {
        if (finder.FindFile("game????.chr")) {
            BOOL more;
            do {
                more = finder.FindNextFile();

                CString fileName = finder.GetFileName();
                fileName = fileName.Mid(4, 4);
                i32 fileIndex;
                sscanf(fileName, "%d", &fileIndex);

                CFile file;
                fileName = finder.GetFileName();
                file.Open(fileName, CFile::modeRead);

                DWORD signature;
                file.Read(&signature, sizeof(signature));
                DWORD characterFlags = 0;
                if (signature == CHARACTER_SIGNATURE) {
                    file.Seek(0x4c, CFile::begin);
                    file.Read(&characterFlags, sizeof(characterFlags));
                }
                file.Close();

                if ((characterFlags & CHARACTER_INCOMPLETE) != 0
                    && (characterFlags & CHARACTER_SPECIAL) == 0) {
                    DeleteFile(fileName);
                }
            } while (more != FALSE);
        }
        finder.Close();
        m_currentIndex = 0;
        LoadCharacter(0);
    }
}

RVA(0x0007ada0, 0x4a8)
void CCharacterSlots::LoadCharacter(i32 index) {
    m_currentIndex = index;

    CMainWindow* mainWindow = static_cast<CMainWindow*>(AfxGetMainWnd());
    CGameWorldState* world = mainWindow->m_world;
    CUnit* unit = world->m_currentUnit;
    if (unit == NULL) {
        unit = new CUnit;
        unit->Initialize(1, 1, 0, 0, 0, world->m_unitDefinitions->m_defaultDefinition, 0, 0, 0, 1);
        world->m_units[1] = unit;
        world->m_currentUnit = unit;
        world->Notify(0x405, 0, 0);
    }

    if (index < 0 || index >= m_characterFileIds.GetSize()) {
        return;
    }

    CFile file(CharacterFileName(m_characterFileIds[m_currentIndex]), CFile::modeRead);
    DWORD signature = CHARACTER_SIGNATURE;
    file.Read(&signature, sizeof(signature));
    file.Read(m_header08, sizeof(m_header08));
    file.Read(m_characterName, sizeof(m_characterName));
    file.Read(m_secondaryName, sizeof(m_secondaryName));
    file.Read(&m_characterFlags, sizeof(m_characterFlags));
    file.Read(&m_characterFlags2, sizeof(m_characterFlags2));
    file.Read(&m_characterData.bytes[0x18], 0x1c);
    file.Read(&m_characterData.bytes[0x34], 0x1c);

    if ((m_characterFlags & CHARACTER_INCOMPLETE) == 0) {
        file.Read(m_characterData.bytes, 0x38);
        file.Read(&unit->m_datae4[0x18], 0x10);
        file.Read(unit->m_data138, 0x20);
        file.Read(unit->m_datae4, 0x10);
        file.Read(&unit->m_datae4[0x0c], 0x10);
        file.Read(&unit->m_value20, sizeof(unit->m_value20));
        file.Read(&unit->m_value24, sizeof(unit->m_value24));
        file.Read(&m_characterData.bytes[0x34], 0x20);
        file.Read(&m_characterData.fields.packedStatistics, sizeof(DWORD));

        i32 detailIndex;
        for (detailIndex = 0; detailIndex < 12; ++detailIndex) {
            if (unit->m_details[detailIndex] != NULL) {
                delete unit->m_details[detailIndex];
                unit->m_details[detailIndex] = NULL;
            }
            file.Read(&unit->m_details[detailIndex], sizeof(unit->m_details[detailIndex]));
        }
        for (detailIndex = 0; detailIndex < 12; ++detailIndex) {
            if (unit->m_details[detailIndex] != NULL) {
                unit->m_details[detailIndex] = new CUnitDetail;
                unit->m_details[detailIndex]->Read(&file);
            }
        }

        i32 wordCount = 0;
        file.Read(&wordCount, sizeof(wordCount));
        m_words.SetSize(wordCount);
        if (wordCount != 0) {
            file.Read(m_words.GetData(), wordCount * sizeof(WORD));
        }

        i32 statisticsIndex;
        for (statisticsIndex = 0; statisticsIndex < 4; ++statisticsIndex) {
            mainWindow->m_characterStatistics->m_values[statisticsIndex] =
                (m_characterData.fields.packedStatistics >> (statisticsIndex * 8)) & 0xff;
            if (mainWindow->m_characterStatistics->m_values[statisticsIndex] > 0x18) {
                mainWindow->m_characterStatistics->m_values[statisticsIndex] = -1;
            }
        }
    } else {
        i32 detailIndex;
        for (detailIndex = 0; detailIndex < 12; ++detailIndex) {
            if (unit->m_details[detailIndex] != NULL) {
                delete unit->m_details[detailIndex];
                unit->m_details[detailIndex] = NULL;
            }
        }
    }

    file.Close();
    unit->m_characterMode = 0x29;
    if ((m_characterFlags2 & 0x40) != 0) {
        unit->m_characterMode = 0x2b;
    }
    if ((m_characterFlags2 & 0x80) != 0) {
        unit->m_characterMode |= 4;
    }
    unit->m_value24 = m_characterData.fields.unitValue;
    if ((m_characterFlags & CHARACTER_INCOMPLETE) != 0) {
        RebuildCharacterDetails();
    }
    unit->FinishLoading();
    world->m_currentUnit = unit;
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

RVA(0x000839b0, 0x31)
CUnitDetail::CUnitDetail() {
    m_value04 = 0;
    m_value18 = 0;
    m_value14 = 0;
    m_serialized06[4] = 0;
    m_data = NULL;
    m_serialized06[3] = 0;
    m_serialized06[2] = 0;
    m_value10 = 1;
    m_value1c = -1;
    m_value20 = -1;
}

RVA_COMPGEN(0x000839f0, 0x1e, ??_GCUnitDetail@@UAEPAXI@Z)

RVA(0x00083ae0, 0x51)
CUnitDetail::~CUnitDetail() {
    if (m_data != NULL) {
        delete m_data;
    }
}

RVA(0x00084910, 0x2b)
void CUnitDetail::Write(CFile* file) {
    file->Write(m_serialized06, sizeof(m_serialized06));
    file->Write(m_data, m_serialized06[4]);
}

RVA(0x00084940, 0x53)
void CUnitDetail::Read(CFile* file) {
    if (m_serialized06[4] != 0) {
        free(m_data);
    }
    file->Read(m_serialized06, sizeof(m_serialized06));
    if (m_serialized06[4] != 0) {
        m_data = static_cast<BYTE*>(malloc(m_serialized06[4]));
        file->Read(m_data, m_serialized06[4]);
    }
}

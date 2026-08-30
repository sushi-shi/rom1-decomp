#include <rva.h>

#include <Serialization/CharacterSlots.h>
#include <Text/ItemNames.h>

#include <string.h>

// The writer reaches three executable-owned configuration globals. Their
// exact starts are fixed independently by its ordered retail relocations.
// clang-format off
DATA(0x001bcecc) extern CGameConfiguration g_gameConfiguration;
DATA(0x001eb4fc) extern BOOL g_requireCharacterDisc;
DATA(0x001f0278) extern char g_characterInput;
// clang-format on

static const DWORD CHARACTER_SIGNATURE = 0x68436c41;
static const DWORD CHARACTER_INCOMPLETE = 0x01;

RVA(0x0007b760, 0x499)
void CCharacterSlots::SaveCharacter(CWordArray* words) {
    CMainWindow* mainWindow = static_cast<CMainWindow*>(AfxGetMainWnd());
    if (mainWindow->m_gameMode == CHARACTER_SLOT_GAME_MODE) {
        return;
    }

    CUnit* unit = mainWindow->m_world->m_currentUnit;

    HKEY registryKey;
    DWORD registryBytes = 0xff;
    CRegistryPathBuffer discPath;
    CRegistryPathBuffer volumeName;
    discPath.characters[0] = 0;
    volumeName.characters[0] = 0;

    RegOpenKeyEx(HKEY_LOCAL_MACHINE, g_gameConfiguration.m_registryKey, 0, KEY_READ, &registryKey);
    if (g_requireCharacterDisc != FALSE) {
        if (RegQueryValueEx(registryKey, "CD", NULL, NULL, discPath.bytes, &registryBytes)
            == ERROR_SUCCESS) {
            DWORD serialNumber;
            DWORD maximumComponentLength;
            DWORD fileSystemFlags;
            strcat(discPath.characters, "\\");
            GetVolumeInformation(
                discPath.characters,
                volumeName.characters,
                0xff,
                &serialNumber,
                &maximumComponentLength,
                &fileSystemFlags,
                NULL,
                0
            );
            if (strcmp(volumeName.characters, "ALLODS") != 0) {
                g_requireCharacterDisc = FALSE;
            }
        } else {
            g_requireCharacterDisc = FALSE;
        }

        if (g_requireCharacterDisc != FALSE) {
            CCharacterSaveWarning* warning = new CCharacterSaveWarning(
                1,
                0x40,
                0x64,
                0x17c,
                0x252,
                static_cast<const char*>(g_textLines[202]),
                0,
                0
            );
            mainWindow->ShowCharacterWarning(warning);
            g_characterInput = '5';
            PostMessage(mainWindow->m_hWnd, 0x41e, 0, 0);
            return;
        }
    }

    DWORD packedStatistics = 0;
    i32 statisticsIndex;
    for (statisticsIndex = 0; statisticsIndex < 4; ++statisticsIndex) {
        packedStatistics |= (mainWindow->m_characterStatistics->m_values[statisticsIndex] & 0xff)
                            << (statisticsIndex * 8);
    }
    m_characterData.fields.packedStatistics = packedStatistics;

    BOOL noWords = words == NULL || words->GetSize() == 0;
    if (noWords == FALSE) {
        m_words.Copy(*words);
        m_characterFlags = m_characterFlags & 0xfffffffe;
        memcpy(
            m_characterData.fields.values,
            words->GetData(),
            sizeof(m_characterData.fields.values)
        );
    } else {
        m_characterData.fields.values[0] = 100;
        m_characterData.fields.values[1] = 0;
        m_characterData.fields.values[2] = 0;
        m_characterData.fields.values[3] = 0;
    }

    CFile file(
        CharacterFileName(m_characterFileIds[m_currentIndex]),
        CFile::modeCreate | CFile::modeWrite
    );
    DWORD signature = CHARACTER_SIGNATURE;
    file.Write(&signature, sizeof(signature));
    file.Write(m_header08, sizeof(m_header08));
    file.Write(m_characterName, sizeof(m_characterName));
    file.Write(m_secondaryName, sizeof(m_secondaryName));
    file.Write(&m_characterFlags, sizeof(m_characterFlags));
    file.Write(&m_characterFlags2, sizeof(m_characterFlags2));
    file.Write(&m_characterData.bytes[0x18], 0x1c);
    file.Write(&m_characterData.bytes[0x34], 0x1c);

    if ((m_characterFlags & CHARACTER_INCOMPLETE) == 0) {
        file.Write(m_characterData.bytes, 0x38);
        file.Write(&unit->m_datae4[0x18], 0x10);
        file.Write(unit->m_data138, 0x20);
        file.Write(unit->m_datae4, 0x10);
        file.Write(&unit->m_datae4[0x0c], 0x10);
        file.Write(&unit->m_value20, sizeof(unit->m_value20));
        file.Write(&unit->m_value24, sizeof(unit->m_value24));
        file.Write(&m_characterData.bytes[0x34], 0x20);
        file.Write(&m_characterData.fields.packedStatistics, sizeof(DWORD));

        i32 detailIndex;
        for (detailIndex = 0; detailIndex < 12; ++detailIndex) {
            file.Write(&unit->m_details[detailIndex], sizeof(unit->m_details[detailIndex]));
        }
        for (detailIndex = 0; detailIndex < 12; ++detailIndex) {
            if (unit->m_details[detailIndex] != NULL) {
                unit->m_details[detailIndex]->Write(&file);
            }
        }

        i32 wordCount = m_words.GetSize();
        file.Write(&wordCount, sizeof(wordCount));
        file.Write(m_words.GetData(), wordCount * sizeof(WORD));
    }
    file.Close();
}

#include <rva.h>

#include <GameLog.h>
#include <Serialization/ReferenceWorld.h>

// These short bodies are naturally emitted from the pinned MFC headers in
// the game-owned TU.  The MFC implementations they call remain vendor code.
RVA_COMPGEN(0x000479b0, 0x11, ?GetSize@CStringArray@@QBEHXZ)
RVA_COMPGEN(0x000c7ec0, 0x18, ?GetAt@CString@@QBEDH@Z)

DATA(0x001c6c18)
char g_missionDescriptionLoadedPrefix[] = "Mission description loaded from ";

RVA(0x000e077d, 0xb0)
CMissionDescriptionSection::CMissionDescriptionSection(const CString& heading) {
    m_name = heading.Mid(1, heading.GetLength() - 2);
}

RVA(0x000e0b06, 0x287)
int CScenarioObjectMap::LoadMissionDescriptions(const CString& path) {
    CStdioFile file;
    if (!file.Open(path, CFile::modeRead | CFile::shareDenyWrite | CFile::typeText, NULL)) {
        return 0;
    }

    CString line;
    CMissionDescriptionSection* section = NULL;

    while (line.GetLength() < 2 || line.GetAt(0) != '[') {
        if (!file.ReadString(line)) {
            file.Close();
            return 1;
        }
    }

    section = new CMissionDescriptionSection(line);
    while (file.ReadString(line)) {
        if (line.GetLength() < 2 || line.GetAt(0) == ';') {
            continue;
        }

        if (line.GetAt(0) == '[') {
            m_descriptions.SetAt(section->m_name, section);
            section = new CMissionDescriptionSection(line);
        } else {
            section->AddLine(line);
        }
    }

    m_descriptions.SetAt(section->m_name, section);
    file.Close();
    LogMessage(CString(g_missionDescriptionLoadedPrefix) + path);
    g_referenceWorld->m_descriptionNeedsDefaults = g_referenceWorld->m_scenarioLoaded == FALSE;
    return 0;
}

RVA(0x000e358b, 0x19ad)
void CScenarioObjectMap::Rebuild(CScenarioResource* resource, BOOL preserveState) {
    (void)resource;
    (void)preserveState;
}

RVA_COMPGEN(0x00115480, 0x2b, ??_GCMissionDescriptionSection@@UAEPAXI@Z)
RVA_COMPGEN(0x001154b0, 0x5a, ??1CMissionDescriptionSection@@UAE@XZ)

RVA_COMPGEN(0x00115530, 0x1e, ?SetAt@CMapStringToPtr@@QAEXPBDPAX@Z)

RVA(0x00115550, 0x2d)
void CMissionDescriptionSection::AddLine(const CString& line) {
    m_lines.SetAtGrow(m_lines.GetSize(), line);
}

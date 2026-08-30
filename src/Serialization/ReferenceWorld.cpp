#include <rva.h>

#include <Serialization/ReferenceWorld.h>

#include <string.h>

CWorldObjectRegistry* DATA(0x0020949c)
g_worldObjectRegistry;

CWorldItemManager* DATA(0x002094b0)
g_worldItemManager;

CWorldMapData* DATA(0x001f2220)
g_worldMapData;

CWorldRuntime* DATA(0x001f211c)
g_worldRuntime;

UINT DATA(0x00209a64)
g_saveRevision;

DATA(0x001c5e9c)
char g_scenarioDirectory[] = "Scenario\\";

RVA_COMPGEN(0x00047c10, 0x10, ??BCString@@QBEPBDXZ)

RVA(0x000d0c97, 0x94b)
void CReferenceWorld::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive << m_value04;
        archive << m_value00;
        archive << m_scenarioName;
        archive << m_value11c;
        archive << m_value124;
        archive << m_value128;
        archive << m_value12c;
        archive << m_value130;
        archive << m_value134;
        archive << m_value138;
        archive << m_value13c;
        archive << m_value148;
        archive << m_value144;
        archive << m_value140;
        archive << m_scenarioPathKind;
        archive << m_mode;

        g_worldObjectRegistry->Serialize(archive);
        m_subsystems->m_quaternary->Serialize(archive);
        if (m_scenarioLoaded != FALSE) {
            archive << static_cast<BYTE>(1);
            m_subsystems->m_primary->Serialize(archive);
            m_subsystems->m_secondary->Serialize(archive);
            g_worldMapData->Serialize(archive);
            g_worldRuntime->Serialize(archive);
            m_subsystems->m_tertiary->Serialize(archive);
        } else {
            archive << static_cast<BYTE>(0);
        }
        archive << static_cast<UINT>(REFERENCE_WORLD_TRAILER);
        archive << g_saveRevision;
    } else {
        ResetSeenTokenIds();
        archive >> m_value04;
        archive >> m_value00;
        archive >> m_scenarioName;
        archive >> m_value11c;
        archive >> m_value124;
        archive >> m_value128;
        archive >> m_value12c;
        archive >> m_value130;
        archive >> m_value134;
        archive >> m_value138;
        archive >> m_value13c;
        archive >> m_value148;
        archive >> m_value144;
        archive >> m_value140;
        archive >> m_scenarioPathKind;

        ReferenceWorldLoadState loadState;
        archive >> loadState.mode;
        if (static_cast<int>(loadState.mode) >= 1 && static_cast<int>(loadState.mode) <= 3) {
            m_mode = loadState.mode;
        }

        g_worldObjectRegistry->Serialize(archive);
        m_subsystems->m_quaternary->Serialize(archive);

        archive >> loadState.hasScenario;
        if (loadState.hasScenario != 0) {
            CWorldObjectIterator objects;
            objects.m_current = objects.First(g_worldObjectRegistry);
            while (objects.m_current != 0) {
                CWorldItemIterator items;
                items.m_current = items.First(
                    objects.m_current->m_itemCollection != 0
                        ? &objects.m_current->m_itemCollection->m_items
                        : 0
                );
                while (items.m_current != 0) {
                    if ((items.m_current->m_flags4c & REFERENCE_WORLD_ITEM_TRANSIENT) == 0) {
                        g_worldItemManager->Remove(items.m_current);
                    }
                    items.m_current = items.Next();
                }
                objects.m_current = objects.Next();
            }

            if (m_subsystems->m_primary == 0) {
                m_subsystems->m_primary = new CScenarioPrimary;
            }
            m_subsystems->m_primary->Serialize(archive);

            if (m_subsystems->m_secondary == 0) {
                m_subsystems->m_secondary = new CScenarioSecondary;
            }
            m_subsystems->m_secondary->Serialize(archive);

            CString scenarioName(m_scenarioName);
            if (m_scenarioPathKind != 0) {
                scenarioName = g_scenarioDirectory + scenarioName;
            }

            CScenarioResource* resource =
                new CScenarioResource(static_cast<const char*>(scenarioName));
            g_worldMapData = new CWorldMapData(resource, g_worldItemManager);
            g_worldMapData->Serialize(archive);

            if (g_worldRuntime == 0) {
                g_worldRuntime = new CWorldRuntime(g_worldMapData, g_worldObjectRegistry);
                g_worldRuntime->Serialize(archive);
            }

            if (m_subsystems->m_tertiary == 0) {
                m_subsystems->m_tertiary = new CScenarioTertiary;
            }
            m_subsystems->m_tertiary->Serialize(archive);

            m_objectMap.Rebuild(resource, FALSE);
            delete resource;
            m_scenarioLoaded = TRUE;
        } else {
            m_scenarioLoaded = FALSE;
        }

        if (loadState.hasScenario != 0) {
            g_worldItemManager->Activate();
            m_subsystems->m_quaternary->Activate();
            g_worldMapData->Activate();
            g_worldRuntime->Activate();
            m_subsystems->m_secondary->Activate();
        } else {
            CWorldObjectIterator objects;
            objects.m_current = objects.First(g_worldObjectRegistry);
            while (objects.m_current != 0) {
                CWorldItemIterator items;
                items.m_current = items.First(
                    objects.m_current->m_itemCollection != 0
                        ? &objects.m_current->m_itemCollection->m_items
                        : 0
                );
                while (items.m_current != 0) {
                    items.m_current->m_value40 = 0;
                    items.m_current->m_value44 = 0;
                    items.m_current->m_value5c = 0;
                    items.m_current = items.Next();
                }
                objects.m_current = objects.Next();
            }
        }

        UINT trailer;
        archive >> trailer;
        if (trailer == REFERENCE_WORLD_TRAILER) {
            archive >> g_saveRevision;
        }
    }

    m_snapshot->Serialize(archive);
}

RVA(0x000d9f44, 0x23)
void ResetSeenTokenIds() {
    memset(g_seenTokenIds, 0, sizeof(g_seenTokenIds));
    g_seenTokenIds[0] = 1;
}

RVA_COMPGEN(0x00114880, 0x2e, ??_GCScenarioResource@@QAEPAXI@Z)

#include <rva.h>

#include <Network/LlDriver.h>

#include <ctype.h>
#include <io.h>
#include <process.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

DATA(0x001c72ec)
char g_ipInfoTemporaryFile[] = "IPINFO.$$$$$$";

DATA(0x001c72fc)
char g_pathSeparator[] = "\\";

DATA(0x001c7300)
char g_ipConfigProgram[] = "IPConfig.exe";

DATA(0x001c7310)
char g_winIpConfigProgram[] = "WinIpCfg.exe";

DATA(0x001c7320)
char g_batchArgument[] = "/BATCH";

DATA(0x001c7328)
char g_allArgument[] = "/ALL";

DATA(0x001c7330)
char g_readMode[] = "r";

DATA(0x001c7334)
char g_descriptionLabel[] = "Description";

DATA(0x001c7340)
char g_unspecifiedIp[] = "0.0.0.0";

DATA(0x001c7348)
char g_ipAddressLabel[] = "IP Address";

DATA(0x001c7354)
char g_defaultAdapter[] = "Default adapter";

DATA(0x001c7364)
char g_defaultIp[] = "0.0.0.0";

RVA(0x000eb323, 0xa2)
CConnectionInfo* CLlDriver::AppendConnectionInfo() {
    if (m_connectionInfo == NULL) {
        m_connectionInfo = static_cast<CConnectionInfo*>(malloc(sizeof(CConnectionInfo)));
        m_connectionInfoCount = 1;
        return m_connectionInfo;
    }

    ++m_connectionInfoCount;
    m_connectionInfo = static_cast<CConnectionInfo*>(
        realloc(m_connectionInfo, m_connectionInfoCount * sizeof(CConnectionInfo))
    );
    return m_connectionInfo + (m_connectionInfoCount - 1);
}

RVA(0x000eba39, 0x36a)
void CLlDriver::LoadIpConnectionInfo() {
    char* temporaryFile = g_ipInfoTemporaryFile;
    char directory[MAX_PATH] = "";
    OSVERSIONINFO version;
    version.dwOSVersionInfoSize = sizeof(version);
    GetVersionEx(&version);

    BOOL isNt = version.dwPlatformId != VER_PLATFORM_WIN32_WINDOWS;
    DWORD directoryLength;
    if (isNt) {
        directoryLength = GetSystemDirectory(directory, sizeof(directory));
    } else {
        directoryLength = GetWindowsDirectory(directory, sizeof(directory));
    }

    if (directory[directoryLength] != '\\') {
        strcat(directory, g_pathSeparator);
    }
    if (isNt) {
        strcat(directory, g_ipConfigProgram);
    } else {
        strcat(directory, g_winIpConfigProgram);
    }

    _spawnlp(_P_WAIT, directory, directory, g_allArgument, g_batchArgument, temporaryFile, NULL);

    CConnectionInfo* connection = NULL;
    FILE* file = fopen(temporaryFile, g_readMode);
    if (file != NULL) {
        const int bufferSize = 0x800;
        char buffer[bufferSize];
        char* end;
        char* value;
        BYTE unusedFlag;

        do {
            if (fgets(buffer, bufferSize, file) == NULL) {
                break;
            }

            unusedFlag = 0;
            char* colon = strchr(buffer, ':');
            if (colon == NULL) {
                continue;
            }

            *colon = '\0';
            value = colon + 1;
            while (isspace(*value)) {
                ++value;
            }

            end = value + strlen(value) - 1;
            while (end != value && isspace(*end)) {
                *end = '\0';
                --end;
            }

            if (strstr(buffer, g_descriptionLabel) != NULL && connection == NULL) {
                connection = AppendConnectionInfo();
                strcpy(connection->m_description, value);
                strcpy(connection->m_address, g_unspecifiedIp);
            } else if (strstr(buffer, g_ipAddressLabel) != NULL && connection != NULL) {
                strcpy(connection->m_address, value);
                connection = NULL;
            }
        } while (TRUE);

        fclose(file);
        _unlink(temporaryFile);
    }

    if (m_connectionInfoCount == 0) {
        if (connection == NULL) {
            connection = AppendConnectionInfo();
        }
        strcpy(connection->m_description, g_defaultAdapter);
        strcpy(connection->m_address, g_defaultIp);
    }
}

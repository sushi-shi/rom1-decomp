#include <rva.h>

#include <Serialization/StringRecordFile.h>

#include <string.h>

RVA_COMPGEN(0x00047a00, 0x2b, ?Add@CStringArray@@QAEHPBD@Z)
RVA_COMPGEN(0x00048140, 0x17, ?RemoveAll@CStringArray@@QAEXXZ)

RVA(0x000d1783, 0x18a)
void CStringRecordFile::ReadRecords() {
    CStdioFile file;
    if (!file.Open(m_path, CFile::modeRead, NULL)) {
        return;
    }

    CString firstLine;
    CString secondLine;
    CString ignoredLine;
    char record[1024];

    RemoveAll();
    while (file.GetPosition() < file.GetLength()) {
        file.ReadString(firstLine);
        file.ReadString(secondLine);
        file.ReadString(ignoredLine);
        file.ReadString(ignoredLine);

        strcpy(record, firstLine);
        record[firstLine.GetLength()] = 1;
        strcpy(record + firstLine.GetLength() + 1, secondLine);
        Add(record);
    }
    file.Close();
}

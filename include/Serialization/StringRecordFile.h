#ifndef ROM1_SERIALIZATION_STRINGRECORDFILE_H
#define ROM1_SERIALIZATION_STRINGRECORDFILE_H

#include <MfcNoInline.h>

// A text-backed CStringArray. Retail fixes CStringArray as the complete
// 0x14-byte base, followed by the source path and its last-write timestamp.
class CStringRecordFile : public CStringArray {
public:
    void ReadRecords();

private:
    CString m_path;
    CTime m_lastWriteTime;
};

#endif // ROM1_SERIALIZATION_STRINGRECORDFILE_H

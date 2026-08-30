#ifndef ROM1_SERIALIZATION_WORLDRUNTIMERECORDS_H
#define ROM1_SERIALIZATION_WORLDRUNTIMERECORDS_H

#include <MfcNoInline.h>

// Player+0x30 owns a separately allocated 32-byte record with this exact raw
// archive contract.  No original class name survives.
class CPlayerArchiveBlock {
public:
    void Serialize(CArchive& archive);

private:
    BYTE m_bytes[0x20];
};

#endif // ROM1_SERIALIZATION_WORLDRUNTIMERECORDS_H

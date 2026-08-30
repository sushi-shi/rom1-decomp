#include <rva.h>

#include <Serialization/ReferenceWorld.h>

RVA(0x0013e840, 0x26)
void CReferenceSnapshot::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

#include <rva.h>

#include <Serialization/SpellObjects.h>

RVA(0x00144a70, 0x23)
void CTokenPayload::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.Write(this, sizeof(*this));
    } else {
        archive.Read(this, sizeof(*this));
    }
}

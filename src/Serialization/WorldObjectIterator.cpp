#include <rva.h>

#include <Serialization/ReferenceWorld.h>

RVA(0x0011f010, 0x10)
CWorldObjectIterator::CWorldObjectIterator() {}

RVA(0x0011f020, 0x50)
CWorldObject* CWorldObjectIterator::First(CWorldObjectRegistry* registry) {
    (void)registry;
    return 0;
}

RVA(0x0011f070, 0x30)
CWorldObject* CWorldObjectIterator::Next() {
    return 0;
}

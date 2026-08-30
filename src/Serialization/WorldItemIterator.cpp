#include <rva.h>

#include <Serialization/ReferenceWorld.h>

RVA(0x0011f280, 0x10)
CWorldItemIterator::CWorldItemIterator() {}

RVA(0x0011f290, 0x50)
CWorldItem* CWorldItemIterator::First(CWorldItemList* list) {
    (void)list;
    return 0;
}

RVA(0x0011f2e0, 0x30)
CWorldItem* CWorldItemIterator::Next() {
    return 0;
}

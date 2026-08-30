#include <rva.h>

#include <Serialization/SpellObjects.h>

RVA(0x00118080, 0xd)
UINT TransformPlayerReference(UINT value) {
    return value ^ 0x5c073f4d;
}

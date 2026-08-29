#ifndef ROM1_RVA_H
#define ROM1_RVA_H

#include <Ints.h>

#if defined(__clang__) && defined(ROM1_EMIT_META)

#define RVA(addr, size) __attribute__((annotate("rva:" #addr " size:" #size), used))

#define OVERRIDE override

#define DATA(addr) __attribute__((annotate("data:" #addr)))

#define RVA_COMPGEN(addr, size, symbol)
#define RVA_DYNINIT(addr, size, owner)
#define DATA_COMPGEN(addr, value) value

#else

#define RVA(addr, size)
#define DATA(addr)
#define OVERRIDE

#define RVA_COMPGEN(addr, size, symbol)
#define RVA_DYNINIT(addr, size, owner)
#define DATA_COMPGEN(addr, value) value

#endif

#endif // ROM1_RVA_H

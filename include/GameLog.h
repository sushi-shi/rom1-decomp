#ifndef ROM1_GAMELOG_H
#define ROM1_GAMELOG_H

#include <MfcNoInline.h>

// The body at 0x037000 is game-owned but not reconstructed here.  Keep its
// evidence-neutral executable label so callers retain the real referent
// without inventing or stubbing an implementation.
extern "C" void FUN_00437000(CString message);

#define LogMessage FUN_00437000

#endif // ROM1_GAMELOG_H

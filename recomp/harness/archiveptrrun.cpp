/* Execute retail CTextPointerVector::Serialize in both CArchive modes and
 * compare its count/raw-word calls plus every resize state transition. */

#include <MfcWin.h>

#include <Ints.h>

#include "recomp.h"

#define RVA_SERIALIZE 0x00069390
#define RVA_WRITE_COUNT_CALL 0x000693ac
#define RVA_READ_COUNT_CALL 0x000693b8
#define RVA_ZERO_FREE_CALL 0x000693cd
#define RVA_INITIAL_ALLOC_CALL 0x000693f2
#define RVA_GROW_ALLOC_CALL 0x00069484
#define RVA_GROW_FREE_CALL 0x000694bb
#define RVA_WRITE_CALL 0x000694ef
#define RVA_READ_CALL 0x00069509

#define MAX_WORDS 512

typedef void(__fastcall* RetailSerialize)(void*, void*, void*);

struct VectorState {
    void* vtable;
    u32* data;
    i32 size;
    i32 maxSize;
    i32 growBy;
};

struct ArchiveState {
    unsigned char beforeMode[0x14];
    u32 mode;
};

static u32 g_input[MAX_WORDS];
static unsigned char g_written[MAX_WORDS * sizeof(u32)];
static u32 g_readCount;
static u32 g_writeCount;
static unsigned int g_writeCountCalls;
static unsigned int g_readCountCalls;
static unsigned int g_writeCalls;
static unsigned int g_readCalls;
static unsigned int g_writeBytes;
static unsigned int g_readBytes;
static unsigned int g_allocCalls;
static unsigned int g_freeCalls;
static unsigned int g_lastAllocBytes;

static void reset_calls() {
    g_writeCount = 0xffffffffu;
    g_writeCountCalls = 0;
    g_readCountCalls = 0;
    g_writeCalls = 0;
    g_readCalls = 0;
    g_writeBytes = 0xffffffffu;
    g_readBytes = 0xffffffffu;
    g_allocCalls = 0;
    g_freeCalls = 0;
    g_lastAllocBytes = 0xffffffffu;
    memset(g_written, 0xcc, sizeof(g_written));
}

static void __fastcall archive_write_count(void*, void*, u32 count) {
    ++g_writeCountCalls;
    g_writeCount = count;
}

static u32 __fastcall archive_read_count(void*, void*) {
    ++g_readCountCalls;
    return g_readCount;
}

static void* __cdecl vector_alloc(unsigned int bytes) {
    ++g_allocCalls;
    g_lastAllocBytes = bytes;
    return malloc(bytes != 0 ? bytes : 1);
}

static void __cdecl vector_free(void* allocation) {
    ++g_freeCalls;
    free(allocation);
}

static void __fastcall archive_write(void*, void*, const void* data, unsigned int bytes) {
    ++g_writeCalls;
    g_writeBytes = bytes;
    if (bytes != 0) {
        memcpy(g_written, data, bytes);
    }
}

static unsigned int __fastcall archive_read(void*, void*, void* data, unsigned int bytes) {
    ++g_readCalls;
    g_readBytes = bytes;
    if (bytes != 0) {
        memcpy(data, g_input, bytes);
    }
    return bytes;
}

static int expected_max_size(i32 count, i32 oldSize, i32 oldMax, i32 growBy) {
    if (count == 0) {
        return 0;
    }
    if (oldMax == 0) {
        return count;
    }
    if (count <= oldMax) {
        return oldMax;
    }
    i32 grow = growBy;
    if (grow == 0) {
        grow = oldSize / 8;
        if (grow < 4) {
            grow = 4;
        } else if (grow > 1024) {
            grow = 1024;
        }
    }
    i32 grown = oldMax + grow;
    return count >= grown ? count : grown;
}

static void call_serialize(VectorState* vector, ArchiveState* archive) {
    ((RetailSerialize)RECOMP_RVA(RVA_SERIALIZE))(vector, 0, archive);
}

static void run_store(RecompCase* tests, i32 count) {
    VectorState vector;
    ArchiveState archive;
    memset(&vector, 0, sizeof(vector));
    memset(&archive, 0, sizeof(archive));
    vector.data = g_input;
    vector.size = count;
    vector.maxSize = count;
    archive.mode = 0;
    reset_calls();

    call_serialize(&vector, &archive);

    recomp_check(tests + 0, g_writeCountCalls, 1);
    recomp_check(tests + 0, g_readCountCalls, 0);
    recomp_check(tests + 0, g_writeCalls, 1);
    recomp_check(tests + 0, g_readCalls, 0);
    recomp_check(tests + 0, g_writeCount, count);
    recomp_check(tests + 0, g_writeBytes, count * sizeof(u32));
    recomp_check(tests + 0, g_allocCalls, 0);
    recomp_check(tests + 0, g_freeCalls, 0);
    recomp_check_mem(tests + 1, g_written, g_input, count * sizeof(u32));
}

static void run_load(RecompCase* tests, i32 count, i32 oldSize, i32 oldMax, i32 growBy) {
    VectorState vector;
    ArchiveState archive;
    i32 expectedMax = expected_max_size(count, oldSize, oldMax, growBy);
    int expectsAllocation = count > oldMax;
    int expectsFree = oldMax != 0 && (count == 0 || count > oldMax);

    memset(&vector, 0, sizeof(vector));
    memset(&archive, 0, sizeof(archive));
    if (oldMax != 0) {
        vector.data = static_cast<u32*>(malloc(oldMax * sizeof(u32)));
        for (i32 index = 0; index < oldMax; ++index) {
            vector.data[index] = 0xccccccccu;
        }
    }
    vector.size = oldSize;
    vector.maxSize = oldMax;
    vector.growBy = growBy;
    archive.mode = 1;
    g_readCount = count;
    reset_calls();

    call_serialize(&vector, &archive);

    recomp_check(tests + 0, g_writeCountCalls, 0);
    recomp_check(tests + 0, g_readCountCalls, 1);
    recomp_check(tests + 0, g_writeCalls, 0);
    recomp_check(tests + 0, g_readCalls, 1);
    recomp_check(tests + 0, g_readBytes, count * sizeof(u32));
    recomp_check(tests + 0, vector.size, count);
    recomp_check(tests + 0, vector.maxSize, expectedMax);
    recomp_check(tests + 0, vector.data != 0, count != 0);
    recomp_check(tests + 0, g_allocCalls, expectsAllocation);
    recomp_check(tests + 0, g_freeCalls, expectsFree);
    if (expectsAllocation) {
        recomp_check(tests + 0, g_lastAllocBytes, expectedMax * sizeof(u32));
    }
    if (count != 0) {
        recomp_check_mem(tests + 1, vector.data, g_input, count * sizeof(u32));
    }
    free(vector.data);
}

int main(int argc, char** argv) {
    RecompCase tests[2];

    if (argc < 3) {
        fprintf(stderr, "usage: %s <ALLODS.EXE> <relocs.tsv>\n", argv[0]);
        return 1;
    }
    if (!recomp_map(argv[1], argv[2])
        || !recomp_patch_rel32(RVA_WRITE_COUNT_CALL, archive_write_count)
        || !recomp_patch_rel32(RVA_READ_COUNT_CALL, archive_read_count)
        || !recomp_patch_rel32(RVA_ZERO_FREE_CALL, vector_free)
        || !recomp_patch_rel32(RVA_INITIAL_ALLOC_CALL, vector_alloc)
        || !recomp_patch_rel32(RVA_GROW_ALLOC_CALL, vector_alloc)
        || !recomp_patch_rel32(RVA_GROW_FREE_CALL, vector_free)
        || !recomp_patch_rel32(RVA_WRITE_CALL, archive_write)
        || !recomp_patch_rel32(RVA_READ_CALL, archive_read)) {
        return 1;
    }

    recomp_case(&tests[0], "archive pointer-vector calls/state");
    recomp_case(&tests[1], "archive pointer-vector raw words");
    recomp_seed(RVA_SERIALIZE);

    for (i32 test = 0; test < 2048; ++test) {
        i32 count = static_cast<i32>(recomp_rand() % (MAX_WORDS + 1));
        for (i32 index = 0; index < count; ++index) {
            g_input[index] = recomp_rand();
        }
        run_store(tests, count);

        switch (test & 3) {
            case 0:
                run_load(tests, count, 0, 0, 0);
                break;
            case 1: {
                i32 capacity = count + static_cast<i32>(recomp_rand() % 17);
                i32 oldSize = capacity == 0 ? 0 : static_cast<i32>(recomp_rand() % (capacity + 1));
                run_load(tests, count, oldSize, capacity, 0);
                break;
            }
            case 2: {
                i32 oldMax = count == 0 ? 8 : count / 2;
                i32 oldSize = oldMax;
                run_load(tests, count, oldSize, oldMax, 0);
                break;
            }
            default: {
                i32 oldMax = count == 0 ? 8 : count / 3;
                i32 oldSize = oldMax;
                i32 growBy = static_cast<i32>(recomp_rand() % 32) + 1;
                run_load(tests, count, oldSize, oldMax, growBy);
                break;
            }
        }
    }
    return recomp_report(tests, 2);
}

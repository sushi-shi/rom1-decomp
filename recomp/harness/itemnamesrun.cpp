/* Execute retail LoadItemNames and compare its headerless little-endian word
 * grammar, odd-byte truncation, lookup order, and map assignments. */

#include <MfcWin.h>

#include <Ints.h>

#include "recomp.h"

#define RVA_LOAD_ITEM_NAMES 0x00068490
#define RVA_RESOURCE_CTOR_CALL 0x000684af
#define RVA_RESOURCE_OPEN_CALL 0x000684c9
#define RVA_RESOURCE_LENGTH_CALL 0x000684d2
#define RVA_MALLOC_CALL 0x000684e0
#define RVA_RESOURCE_READ_CALL 0x000684f4
#define RVA_RESOURCE_CLOSE_CALL 0x000684fd
#define RVA_TEXT_LOOKUP_CALL 0x0006850f
#define RVA_MAP_INSERT_CALL 0x0006851f
#define RVA_FREE_CALL 0x00068534
#define RVA_RESOURCE_DTOR_CALL 0x00068548

#define MAX_INPUT_BYTES 1025
#define MAX_IDS (MAX_INPUT_BYTES / 2)

typedef void(__cdecl* RetailLoadItemNames)();

struct CapturedAssignment {
    u16 key;
    void* value;
};

static const unsigned char* g_input;
static unsigned int g_inputSize;
static unsigned int g_allocatedBytes;
static unsigned int g_readBytes;
static unsigned int g_ctorCalls;
static unsigned int g_openCalls;
static unsigned int g_closeCalls;
static unsigned int g_dtorCalls;
static unsigned int g_lookupCalls;
static unsigned int g_mapCalls;
static int g_pathMatches;
static unsigned long g_textValues[MAX_IDS];
static CapturedAssignment g_assignments[MAX_IDS];

static void reset_capture(const unsigned char* input, unsigned int size) {
    g_input = input;
    g_inputSize = size;
    g_allocatedBytes = 0xffffffffu;
    g_readBytes = 0xffffffffu;
    g_ctorCalls = 0;
    g_openCalls = 0;
    g_closeCalls = 0;
    g_dtorCalls = 0;
    g_lookupCalls = 0;
    g_mapCalls = 0;
    g_pathMatches = 0;
    memset(g_assignments, 0xcc, sizeof(g_assignments));
}

static void* text_value(unsigned int index) {
    return &g_textValues[index];
}

static void __fastcall resource_ctor(void*, void*) {
    ++g_ctorCalls;
}

static int __fastcall resource_open(void*, void*, const char* path, unsigned int, unsigned int) {
    ++g_openCalls;
    g_pathMatches = strcmp(path, "main\\text\\itemname.bin") == 0;
    return 1;
}

static unsigned int __fastcall resource_length(void*, void*) {
    return g_inputSize;
}

static void* __cdecl retail_alloc(unsigned int size) {
    g_allocatedBytes = size;
    return malloc(size != 0 ? size : 1);
}

static unsigned int __fastcall resource_read(void*, void*, void* output, unsigned int size) {
    g_readBytes = size;
    if (size != 0) {
        memcpy(output, g_input, size);
    }
    return size;
}

static void __fastcall resource_close(void*, void*) {
    ++g_closeCalls;
}

static void* __fastcall text_lookup(void*, void*, i32 index) {
    ++g_lookupCalls;
    return text_value(static_cast<unsigned int>(index));
}

static void** __fastcall map_insert(void*, void*, u16 key) {
    CapturedAssignment* assignment = &g_assignments[g_mapCalls++];
    assignment->key = key;
    assignment->value = 0;
    return &assignment->value;
}

static void __cdecl retail_free(void* allocation) {
    free(allocation);
}

static void __fastcall resource_dtor(void*, void*) {
    ++g_dtorCalls;
}

static u16 read_id(const unsigned char* input, unsigned int index) {
    unsigned int at = index * 2;
    return static_cast<u16>(input[at] | static_cast<u16>(input[at + 1]) << 8);
}

static void run_case(RecompCase* tests, const unsigned char* input, unsigned int size) {
    unsigned int expectedCount = size >> 1;
    unsigned int expectedBytes = expectedCount * 2;
    reset_capture(input, size);

    ((RetailLoadItemNames)RECOMP_RVA(RVA_LOAD_ITEM_NAMES))();

    recomp_check(tests + 0, g_ctorCalls, 1);
    recomp_check(tests + 0, g_openCalls, 1);
    recomp_check(tests + 0, g_pathMatches, 1);
    recomp_check(tests + 0, g_closeCalls, 1);
    recomp_check(tests + 0, g_dtorCalls, 1);
    recomp_check(tests + 0, g_allocatedBytes, expectedBytes);
    recomp_check(tests + 0, g_readBytes, expectedBytes);
    recomp_check(tests + 0, g_lookupCalls, expectedCount);
    recomp_check(tests + 0, g_mapCalls, expectedCount);

    for (unsigned int index = 0; index < expectedCount; ++index) {
        recomp_check(tests + 1, g_assignments[index].key, read_id(input, index));
        recomp_check(tests + 1, g_assignments[index].value == text_value(index), 1);
    }
}

int main(int argc, char** argv) {
    RecompCase tests[2];
    unsigned char input[MAX_INPUT_BYTES];

    if (argc < 3) {
        fprintf(stderr, "usage: %s <ALLODS.EXE> <relocs.tsv>\n", argv[0]);
        return 1;
    }
    if (!recomp_map(argv[1], argv[2]) || !recomp_patch_rel32(RVA_RESOURCE_CTOR_CALL, resource_ctor)
        || !recomp_patch_rel32(RVA_RESOURCE_OPEN_CALL, resource_open)
        || !recomp_patch_rel32(RVA_RESOURCE_LENGTH_CALL, resource_length)
        || !recomp_patch_rel32(RVA_MALLOC_CALL, retail_alloc)
        || !recomp_patch_rel32(RVA_RESOURCE_READ_CALL, resource_read)
        || !recomp_patch_rel32(RVA_RESOURCE_CLOSE_CALL, resource_close)
        || !recomp_patch_rel32(RVA_TEXT_LOOKUP_CALL, text_lookup)
        || !recomp_patch_rel32(RVA_MAP_INSERT_CALL, map_insert)
        || !recomp_patch_rel32(RVA_FREE_CALL, retail_free)
        || !recomp_patch_rel32(RVA_RESOURCE_DTOR_CALL, resource_dtor)) {
        return 1;
    }

    recomp_case(&tests[0], "item-name file/control behavior");
    recomp_case(&tests[1], "item-name ID and text assignments");
    recomp_seed(RVA_LOAD_ITEM_NAMES);

    run_case(tests, input, 0);
    input[0] = 0xee;
    run_case(tests, input, 1);
    for (unsigned int test = 0; test < 2048; ++test) {
        unsigned int size = recomp_rand() % (MAX_INPUT_BYTES + 1);
        for (unsigned int index = 0; index < size; ++index) {
            input[index] = static_cast<unsigned char>(recomp_rand());
        }
        run_case(tests, input, size);
    }
    return recomp_report(tests, 2);
}

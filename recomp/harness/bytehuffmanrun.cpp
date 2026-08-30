/* Execute the retail network Huffman packer and compare it with the VC5
 * reconstruction. Inputs and frequency tables are fabricated; the game is
 * never started. */

#include "recomp.h"

#include <Codec/ByteHuffman.h>

#define RVA_PACKER_CTOR 0x000ef383
#define RVA_CLEAR_STATISTICS 0x000ef3b1
#define RVA_COUNT_SYMBOLS 0x000ef3d4
#define RVA_REBUILD_TREE 0x000ef4d0
#define RVA_BUILD_CODES 0x000ef7da
#define RVA_DESTROY_TREE 0x000ef8b2
#define RVA_PACK 0x000ef939
#define RVA_UNPACK 0x000efa04

#define RVA_REBUILD_ALLOC_CALL 0x000ef578
#define RVA_INSERT_ONE_ALLOC_CALL 0x000ef69f
#define RVA_INSERT_ZERO_ALLOC_CALL 0x000ef70a
#define RVA_DESTROY_FREE_CALL 0x000ef912

/* VC5 does not accept __thiscall on a function-pointer typedef. A fastcall
 * shim has the same ECX `this` register; its unused second argument occupies
 * EDX, leaving the real method arguments on the stack in thiscall order. */
typedef void(__fastcall* RetailNoArgs)(void*, void*);
typedef void(__fastcall* RetailCount)(void*, void*, u8*, i32);
typedef i32(__fastcall* RetailPack)(void*, void*, u8*, i32, u32*);
typedef i32(__fastcall* RetailUnpack)(void*, void*, u32*, i32, u8*, i32);

static void* __cdecl retail_alloc(unsigned int size) {
    return malloc(size ? size : 1);
}

static void __cdecl retail_free(void* allocation) {
    free(allocation);
}

static void retail_call(unsigned long rva, void* packer) {
    ((RetailNoArgs)RECOMP_RVA(rva))(packer, 0);
}

static unsigned long fixture_hash(
    unsigned long hash, const void* bytes, unsigned long size
    ) {
    const unsigned char* cursor = (const unsigned char*)bytes;
    unsigned long index;

    for (index = 0; index < size; ++index) {
        hash ^= cursor[index];
        hash *= 0x01000193u;
    }
    return hash;
}

static void fill_statistics(i32* frequencies, i32 iteration) {
    i32 index;

    for (index = 0; index < 256; ++index) {
        if (iteration == 0) {
            frequencies[index] = 0;
        } else if (iteration == 1) {
            frequencies[index] = 1;
        } else if (iteration == 2) {
            frequencies[index] = index;
        } else if (iteration == 3) {
            frequencies[index] = 255 - index;
        } else {
            /* The mask deliberately creates equal-key groups, exercising the
             * observable VC5 qsort permutation as well as the tree weights. */
            frequencies[index] = (i32)(recomp_rand() & 0x3ff);
        }
    }
}

static void compare_tree_case(RecompCase* tests, i32 iteration) {
    ByteHuffmanPacker ours;
    unsigned char retailStorage[sizeof(ByteHuffmanPacker)];
    i32* retailFrequencies = (i32*)(retailStorage + 0x800);
    u8 input[513];
    u32 oursPacked[4096];
    u32 retailPacked[4096];
    u8 oursDecoded[513];
    u8 retailDecoded[513];
    i32 inputSize;
    i32 oursBits;
    i32 retailBits;
    i32 oursCount;
    i32 retailCount;
    i32 index;

    memset(retailStorage, 0, sizeof(retailStorage));
    retail_call(RVA_PACKER_CTOR, retailStorage);
    fill_statistics(ours.frequencies, iteration);
    memcpy(retailFrequencies, ours.frequencies, sizeof(ours.frequencies));

    ours.RebuildTree();
    ours.BuildCodes();
    retail_call(RVA_REBUILD_TREE, retailStorage);
    retail_call(RVA_BUILD_CODES, retailStorage);
    if (iteration < 4) {
        unsigned long hash = fixture_hash(0x811c9dc5u, retailStorage, 0x800);
        printf("fixture codebook[%d] fnv1a32=%08lx\n", iteration, hash);
    }
    recomp_check_mem(&tests[0], ours.codes, retailStorage, sizeof(ours.codes));
    recomp_check_mem(
        &tests[1], ours.codeBits, retailStorage + 0x400, sizeof(ours.codeBits)
    );

    inputSize = iteration == 0 ? 256 : (i32)(recomp_rand() % 512) + 1;
    for (index = 0; index < inputSize; ++index) {
        input[index] = iteration == 0 ? (u8)index : (u8)recomp_rand();
    }
    memset(oursPacked, 0xa5, sizeof(oursPacked));
    memset(retailPacked, 0xa5, sizeof(retailPacked));
    oursBits = ours.Pack(input, inputSize, oursPacked);
    retailBits = ((RetailPack)RECOMP_RVA(RVA_PACK))(
        retailStorage, 0, input, inputSize, retailPacked
    );
    if (iteration == 0) {
        unsigned long hash = fixture_hash(
            0x811c9dc5u, retailPacked, (unsigned long)ByteCountForBits(retailBits)
        );
        printf(
            "fixture zero/all-symbols bits=%d fnv1a32=%08lx\n", retailBits, hash
        );
    }
    recomp_check(&tests[2], oursBits, retailBits);
    if (oursBits == retailBits) {
        recomp_check_mem(
            &tests[3], oursPacked, retailPacked, (size_t)ByteCountForBits(oursBits)
        );
    } else {
        recomp_check(&tests[3], 0, 1);
    }

    oursCount = ours.Unpack(oursPacked, oursBits, oursDecoded, sizeof(oursDecoded));
    retailCount = ((RetailUnpack)RECOMP_RVA(RVA_UNPACK))(
        retailStorage,
        0,
        retailPacked,
        retailBits,
        retailDecoded,
        sizeof(retailDecoded)
    );
    recomp_check(&tests[4], oursCount, retailCount);
    if (oursCount == retailCount) {
        recomp_check_mem(&tests[5], oursDecoded, retailDecoded, oursCount);
    } else {
        recomp_check(&tests[5], 0, 1);
    }
    recomp_check(
        &tests[6],
        oursCount == inputSize && memcmp(oursDecoded, input, inputSize) == 0,
        retailCount == inputSize && memcmp(retailDecoded, input, inputSize) == 0
    );

    ours.DestroyTree();
    retail_call(RVA_DESTROY_TREE, retailStorage);
}

static void compare_counter(RecompCase* test) {
    ByteHuffmanPacker ours;
    unsigned char retailStorage[sizeof(ByteHuffmanPacker)];
    u8 input[1024];
    i32 iteration;
    i32 index;

    memset(retailStorage, 0, sizeof(retailStorage));
    retail_call(RVA_PACKER_CTOR, retailStorage);
    ours.ClearStatistics();
    retail_call(RVA_CLEAR_STATISTICS, retailStorage);
    for (iteration = 0; iteration < 4096; ++iteration) {
        i32 size = (i32)(recomp_rand() % sizeof(input));
        for (index = 0; index < size; ++index) {
            input[index] = (u8)recomp_rand();
        }
        ours.CountSymbols(input, size);
        ((RetailCount)RECOMP_RVA(RVA_COUNT_SYMBOLS))(retailStorage, 0, input, size);
        recomp_check_mem(test, ours.frequencies, retailStorage + 0x800, 0x400);
    }
}

int main(int argc, char** argv) {
    RecompCase tests[8];
    i32 iteration;

    if (argc < 3) {
        fprintf(stderr, "usage: %s <ALLODS.EXE> <relocs.tsv>\n", argv[0]);
        return 1;
    }
    if (!recomp_map(argv[1], argv[2])
        || !recomp_patch_rel32(RVA_REBUILD_ALLOC_CALL, retail_alloc)
        || !recomp_patch_rel32(RVA_INSERT_ONE_ALLOC_CALL, retail_alloc)
        || !recomp_patch_rel32(RVA_INSERT_ZERO_ALLOC_CALL, retail_alloc)
        || !recomp_patch_rel32(RVA_DESTROY_FREE_CALL, retail_free)) {
        return 1;
    }

    recomp_case(&tests[0], "generated code values");
    recomp_case(&tests[1], "generated code bit lengths");
    recomp_case(&tests[2], "packed bit count");
    recomp_case(&tests[3], "packed bytes");
    recomp_case(&tests[4], "unpacked byte count");
    recomp_case(&tests[5], "unpacked bytes");
    recomp_case(&tests[6], "pack/unpack restores input");
    recomp_case(&tests[7], "accumulated frequency table");
    recomp_seed(0x000ef939u);

    for (iteration = 0; iteration < 1024; ++iteration) {
        compare_tree_case(tests, iteration);
    }
    compare_counter(&tests[7]);
    return recomp_report(tests, 8);
}

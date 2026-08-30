/* Execute the retail word-RLE encoder/decoder and compare both outputs with
 * the exact VC5 objects linked from build/objdiff/base/. Inputs are fabricated;
 * this never starts the game. */

#include "recomp.h"

#include <Codec/WordRle.h>

#define RVA_ENCODE 0x0011f130
#define RVA_DECODE 0x0011f1e0
#define RVA_ENCODE_ALLOC_CALL 0x0011f149
#define RVA_DECODE_ALLOC_CALL 0x0011f208
#define RVA_ENCODE_MEMCPY_CALL 0x001271cb
#define RVA_DECODE_MEMCPY_CALL 0x001272c3

typedef void(__cdecl* RetailEncode)(u16*, i32, u8**, i32*);
typedef void(__cdecl* RetailDecode)(u8*, i32, u16**, i32*);

/* Retail requests exactly 2*wordCount bytes but writes a four-byte header and
 * token overhead. The shipped process relies on heap rounding. Give both the
 * linked candidate and mapped retail deterministic guard slack so a long
 * oracle sweep tests codec bytes without corrupting the harness allocator. */
void* __cdecl operator new(unsigned int size) {
    return malloc(size + 16);
}

void __cdecl operator delete(void* allocation) {
    free(allocation);
}

static void* __cdecl retail_alloc(unsigned int size) {
    return malloc((size ? size : 1) + 16);
}

static void* __cdecl retail_copy(void* destination, const void* source, unsigned int size) {
    return memcpy(destination, source, size);
}

static void compare_one(RecompCase* tests, u16* padded, i32 count) {
    ByteIntPointer oursEncoded;
    u8* retailEncoded = 0;
    i32 oursSize = 0;
    i32 retailSize = 0;
    u16* oursDecoded = 0;
    u16* retailDecoded = 0;
    i32 oursCount = 0;
    i32 retailCount = 0;
    ByteIntPointer oursInput;

    EncodeWordRle(padded, count, &oursEncoded, &oursSize);
    ((RetailEncode)RECOMP_RVA(RVA_ENCODE))(padded, count, &retailEncoded, &retailSize);
    recomp_check(&tests[0], oursSize, retailSize);
    if (oursSize == retailSize) {
        recomp_check_mem(&tests[1], oursEncoded.bytes, retailEncoded, oursSize);
    } else {
        recomp_check(&tests[1], 0, 1);
    }

    oursInput.bytes = oursEncoded.bytes;
    DecodeWordRle(oursInput, oursSize, &oursDecoded, &oursCount);
    ((RetailDecode)RECOMP_RVA(RVA_DECODE))(retailEncoded, retailSize, &retailDecoded, &retailCount);
    recomp_check(&tests[2], oursCount, retailCount);
    if (oursCount == retailCount) {
        recomp_check_mem(&tests[3], oursDecoded, retailDecoded, oursCount * sizeof(u16));
    } else {
        recomp_check(&tests[3], 0, 1);
    }
    recomp_check(
        &tests[4],
        oursCount == count && memcmp(oursDecoded, padded, count * sizeof(u16)) == 0,
        retailCount == count && memcmp(retailDecoded, padded, count * sizeof(u16)) == 0
    );

    delete[] oursEncoded.bytes;
    delete[] oursDecoded;
    free(retailEncoded);
    free(retailDecoded);
}

int main(int argc, char** argv) {
    RecompCase tests[5];
    u16* padded;
    i32 iteration;
    i32 index;

    if (argc < 3) {
        fprintf(stderr, "usage: %s <ALLODS.EXE> <relocs.tsv>\n", argv[0]);
        return 1;
    }
    if (!recomp_map(argv[1], argv[2]) || !recomp_patch_rel32(RVA_ENCODE_ALLOC_CALL, retail_alloc)
        || !recomp_patch_rel32(RVA_DECODE_ALLOC_CALL, retail_alloc)
        || !recomp_patch_rel32(RVA_ENCODE_MEMCPY_CALL, retail_copy)
        || !recomp_patch_rel32(RVA_DECODE_MEMCPY_CALL, retail_copy)) {
        return 1;
    }

    recomp_case(&tests[0], "encoded byte count");
    recomp_case(&tests[1], "encoded bytes");
    recomp_case(&tests[2], "decoded word count");
    recomp_case(&tests[3], "decoded words");
    recomp_case(&tests[4], "encode/decode restores input");
    recomp_seed(0x11f130u);

    padded = new u16[257];
    for (iteration = 0; iteration < 32768; ++iteration) {
        i32 count = (i32)(recomp_rand() % 256) + 1;
        for (index = 0; index < count; ++index) {
            padded[index] = (u16)recomp_rand();
        }
        padded[count] = (iteration & 1) ? padded[count - 1] : (u16)~padded[count - 1];
        compare_one(tests, padded, count);
    }

    for (index = 0; index < 130; ++index) {
        padded[index] = 7;
    }
    padded[130] = 7;
    compare_one(tests, padded, 130);

    for (index = 0; index < 130; ++index) {
        padded[index] = (u16)index;
    }
    padded[130] = 0xffff;
    compare_one(tests, padded, 130);

    delete[] padded;
    return recomp_report(tests, 5);
}

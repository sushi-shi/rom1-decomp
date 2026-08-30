/* Execute all recovered TableLine-family serializers in mapped retail code.
 * The exact retail CString operators remain in the call path; only primitive
 * CArchive byte I/O and CString buffer allocation are redirected. */

#include <MfcWin.h>

#include <Ints.h>

#include "recomp.h"

#define RVA_TABLE_LINE 0x000df278
#define RVA_WORD_BLOCK 0x000df2c6
#define RVA_RAW_BLOCK 0x000df322
#define RVA_WORD_BLOCK_LABEL 0x000df42a
#define RVA_STRING_PAIR 0x000df63a
#define RVA_STRING_DECADE 0x000dfe42
#define RVA_BASE_ONLY 0x000dffcd
#define RVA_LABEL 0x000e03d2

/* Primitive calls inside the exact VC5 SP2 CString archive operators. */
#define RVA_CSTRING_PUT_BYTE_SHORT 0x0017b989
#define RVA_CSTRING_PUT_BYTE_WORD 0x0017b99c
#define RVA_CSTRING_PUT_WORD 0x0017b9ab
#define RVA_CSTRING_PUT_BYTE_DWORD 0x0017b9b2
#define RVA_CSTRING_PUT_WORD_DWORD 0x0017b9bf
#define RVA_CSTRING_PUT_DWORD 0x0017b9cc
#define RVA_CSTRING_WRITE 0x0017b9da
#define RVA_CSTRING_GET_BUFFER 0x0017ba2c
#define RVA_CSTRING_READ 0x0017ba3b
#define RVA_LENGTH_GET_BYTE 0x0017ba90
#define RVA_LENGTH_GET_WORD 0x0017baa8
#define RVA_LENGTH_GET_DWORD 0x0017bac9

/* Direct raw field calls in the recovered game serializers. */
#define RVA_WORD_BLOCK_WRITE 0x000df2f1
#define RVA_WORD_BLOCK_READ 0x000df304
#define RVA_RAW_BLOCK_WRITE 0x000df351
#define RVA_RAW_BLOCK_READ 0x000df374
#define RVA_WORD_LABEL_WRITE 0x000df455
#define RVA_WORD_LABEL_READ 0x000df478

#define MAX_STRING 65534
#define MAX_STRINGS 12
#define MAX_STREAM 131072
#define MAX_OBJECT 0x80

typedef void(__fastcall* RetailSerialize)(void*, void*, void*);

struct ArchiveState {
    unsigned char beforeMode[0x14];
    u32 mode;
};

/* CStringData is the three DWORDs immediately before m_pchData. */
struct StringStorage {
    i32 refs;
    i32 length;
    i32 allocation;
    unsigned char data[MAX_STRING + 1];
};

enum VariantKind {
    VARIANT_BASE,
    VARIANT_WORD_BLOCK,
    VARIANT_RAW_BLOCK,
    VARIANT_WORD_BLOCK_LABEL,
    VARIANT_STRING_PAIR,
    VARIANT_STRING_DECADE,
    VARIANT_LABEL
};

struct Variant {
    const char* name;
    u32 rva;
    VariantKind kind;
    int strings;
};

static const Variant g_variants[] = {
    {"base", RVA_TABLE_LINE, VARIANT_BASE, 1},
    {"word block", RVA_WORD_BLOCK, VARIANT_WORD_BLOCK, 1},
    {"raw block", RVA_RAW_BLOCK, VARIANT_RAW_BLOCK, 1},
    {"word block + label", RVA_WORD_BLOCK_LABEL, VARIANT_WORD_BLOCK_LABEL, 2},
    {"string pair", RVA_STRING_PAIR, VARIANT_STRING_PAIR, 3},
    {"string decade", RVA_STRING_DECADE, VARIANT_STRING_DECADE, 11},
    {"base only", RVA_BASE_ONLY, VARIANT_BASE, 1},
    {"label", RVA_LABEL, VARIANT_LABEL, 2},
};

static StringStorage g_inputStrings[MAX_STRINGS];
static StringStorage g_outputStrings[MAX_STRINGS];
static void* g_arraySlots[MAX_STRINGS];
static void* g_nestedVtable[3];
static unsigned char g_raw[0x48];
static unsigned char g_stream[MAX_STREAM];
static unsigned char g_expected[MAX_STREAM];
static unsigned int g_streamAt;
static unsigned int g_streamSize;
static unsigned int g_expectedAt;
static unsigned int g_outputCount;
static unsigned int g_nestedCalls;
static u32 g_nestedInput[2];
static u32 g_nestedOutput[2];
static int g_streamFailed;

static int stream_write(const void* data, unsigned int size) {
    if (size > MAX_STREAM - g_streamAt) {
        g_streamFailed = 1;
        return 0;
    }
    memcpy(g_stream + g_streamAt, data, size);
    g_streamAt += size;
    if (g_streamAt > g_streamSize) {
        g_streamSize = g_streamAt;
    }
    return 1;
}

static int stream_read(void* data, unsigned int size) {
    if (size > g_streamSize - g_streamAt) {
        g_streamFailed = 1;
        memset(data, 0, size);
        return 0;
    }
    memcpy(data, g_stream + g_streamAt, size);
    g_streamAt += size;
    return 1;
}

static void expected_write(const void* data, unsigned int size) {
    if (size > MAX_STREAM - g_expectedAt) {
        g_streamFailed = 1;
        return;
    }
    memcpy(g_expected + g_expectedAt, data, size);
    g_expectedAt += size;
}

static void expected_byte(u32 value) {
    unsigned char byte = static_cast<unsigned char>(value);
    expected_write(&byte, 1);
}

static void expected_word(u32 value) {
    unsigned char bytes[2];
    bytes[0] = static_cast<unsigned char>(value);
    bytes[1] = static_cast<unsigned char>(value >> 8);
    expected_write(bytes, 2);
}

static void expected_dword(u32 value) {
    unsigned char bytes[4];
    bytes[0] = static_cast<unsigned char>(value);
    bytes[1] = static_cast<unsigned char>(value >> 8);
    bytes[2] = static_cast<unsigned char>(value >> 16);
    bytes[3] = static_cast<unsigned char>(value >> 24);
    expected_write(bytes, 4);
}

static void expected_string(const StringStorage* string) {
    u32 length = static_cast<u32>(string->length);
    if (length < 0xff) {
        expected_byte(length);
    } else if (length < 0xfffe) {
        expected_byte(0xff);
        expected_word(length);
    } else {
        expected_byte(0xff);
        expected_word(0xffff);
        expected_dword(length);
    }
    expected_write(string->data, length);
}

static void* __fastcall archive_put_byte(void* archive, void*, u32 value) {
    unsigned char byte = static_cast<unsigned char>(value);
    stream_write(&byte, 1);
    return archive;
}

static void* __fastcall archive_put_word(void* archive, void*, u32 value) {
    unsigned char bytes[2];
    bytes[0] = static_cast<unsigned char>(value);
    bytes[1] = static_cast<unsigned char>(value >> 8);
    stream_write(bytes, 2);
    return archive;
}

static void* __fastcall archive_put_dword(void* archive, void*, u32 value) {
    unsigned char bytes[4];
    bytes[0] = static_cast<unsigned char>(value);
    bytes[1] = static_cast<unsigned char>(value >> 8);
    bytes[2] = static_cast<unsigned char>(value >> 16);
    bytes[3] = static_cast<unsigned char>(value >> 24);
    stream_write(bytes, 4);
    return archive;
}

static void* __fastcall archive_get_byte(void* archive, void*, unsigned char* value) {
    stream_read(value, 1);
    return archive;
}

static void* __fastcall archive_get_word(void* archive, void*, u16* value) {
    unsigned char bytes[2];
    stream_read(bytes, 2);
    *value = static_cast<u16>(bytes[0] | (static_cast<u16>(bytes[1]) << 8));
    return archive;
}

static void* __fastcall archive_get_dword(void* archive, void*, u32* value) {
    unsigned char bytes[4];
    stream_read(bytes, 4);
    *value = static_cast<u32>(bytes[0]) | (static_cast<u32>(bytes[1]) << 8)
             | (static_cast<u32>(bytes[2]) << 16) | (static_cast<u32>(bytes[3]) << 24);
    return archive;
}

static void __fastcall archive_write(void*, void*, const void* data, unsigned int size) {
    stream_write(data, size);
}

static unsigned int __fastcall archive_read(void*, void*, void* data, unsigned int size) {
    return stream_read(data, size) ? size : 0;
}

static unsigned char* __fastcall string_get_buffer(void* string, void*, int length) {
    if (length < 0 || length > MAX_STRING || g_outputCount >= MAX_STRINGS) {
        g_streamFailed = 1;
        return 0;
    }
    StringStorage* storage = &g_outputStrings[g_outputCount++];
    storage->refs = 1;
    storage->length = length;
    storage->allocation = length;
    storage->data[length] = 0;
    *static_cast<unsigned char**>(string) = storage->data;
    return storage->data;
}

static void __fastcall nested_serialize(void*, void*, ArchiveState* archive) {
    unsigned int index = g_nestedCalls++;
    if (index >= 2) {
        g_streamFailed = 1;
        return;
    }
    if (archive->mode == 0) {
        stream_write(&g_nestedInput[index], sizeof(u32));
    } else {
        stream_read(&g_nestedOutput[index], sizeof(u32));
    }
}

static void init_string(StringStorage* string, unsigned int length, u32 salt) {
    string->refs = 1;
    string->length = static_cast<i32>(length);
    string->allocation = static_cast<i32>(length);
    for (unsigned int index = 0; index < length; ++index) {
        string->data[index] =
            static_cast<unsigned char>((salt + index * 37u + (index >> 3)) & 0xff);
    }
    string->data[length] = 0;
}

static unsigned int case_length(unsigned int test, unsigned int field, unsigned int count) {
    static const unsigned int boundary[] = {0, 1, 2, 17, 254, 255, 256, 65533, 65534};
    if (field == test % count) {
        return boundary[(test / count) % (sizeof(boundary) / sizeof(boundary[0]))];
    }
    return recomp_rand() % 65;
}

static void prepare_inputs(unsigned int test, unsigned int count) {
    unsigned int index;
    for (index = 0; index < count; ++index) {
        init_string(&g_inputStrings[index], case_length(test, index, count), recomp_rand());
    }
    for (index = 0; index < sizeof(g_raw); ++index) {
        g_raw[index] = static_cast<unsigned char>(recomp_rand());
    }
    g_nestedInput[0] = recomp_rand();
    g_nestedInput[1] = recomp_rand();
}

static void put_pointer(unsigned char* object, unsigned int offset, void* value) {
    *reinterpret_cast<void**>(object + offset) = value;
}

static void prepare_object(unsigned char* object, const Variant* variant, int loading) {
    int index;
    memset(object, 0xcc, MAX_OBJECT);
    put_pointer(object, 4, loading ? 0 : g_inputStrings[0].data);
    put_pointer(object, 8, g_nestedVtable);
    switch (variant->kind) {
        case VARIANT_BASE:
            break;
        case VARIANT_WORD_BLOCK:
            memcpy(object + 0x1c, g_raw, 10);
            put_pointer(object, 0x28, g_nestedVtable);
            break;
        case VARIANT_RAW_BLOCK:
            memcpy(object + 0x20, g_raw, 0x48);
            break;
        case VARIANT_WORD_BLOCK_LABEL:
            memcpy(object + 0x1c, g_raw, 10);
            put_pointer(object, 0x28, g_nestedVtable);
            put_pointer(object, 0x3c, loading ? 0 : g_inputStrings[1].data);
            break;
        case VARIANT_STRING_PAIR:
        case VARIANT_STRING_DECADE:
            put_pointer(object, 0x1c, g_nestedVtable);
            if (loading) {
                memset(g_arraySlots, 0, sizeof(g_arraySlots));
            } else {
                for (index = 1; index < variant->strings; ++index) {
                    g_arraySlots[index - 1] = g_inputStrings[index].data;
                }
            }
            put_pointer(object, 0x20, g_arraySlots);
            break;
        case VARIANT_LABEL:
            put_pointer(object, 0x1c, loading ? 0 : g_inputStrings[1].data);
            break;
    }
}

static void build_expected(const Variant* variant) {
    int index;
    g_expectedAt = 0;
    switch (variant->kind) {
        case VARIANT_BASE:
            expected_string(&g_inputStrings[0]);
            expected_dword(g_nestedInput[0]);
            break;
        case VARIANT_WORD_BLOCK:
            expected_string(&g_inputStrings[0]);
            expected_dword(g_nestedInput[0]);
            expected_write(g_raw, 10);
            expected_dword(g_nestedInput[1]);
            break;
        case VARIANT_RAW_BLOCK:
            expected_string(&g_inputStrings[0]);
            expected_write(g_raw, 0x48);
            break;
        case VARIANT_WORD_BLOCK_LABEL:
            expected_string(&g_inputStrings[0]);
            expected_dword(g_nestedInput[0]);
            expected_write(g_raw, 1);
            expected_string(&g_inputStrings[1]);
            break;
        case VARIANT_STRING_PAIR:
        case VARIANT_STRING_DECADE:
            expected_string(&g_inputStrings[0]);
            expected_dword(g_nestedInput[0]);
            for (index = 1; index < variant->strings; ++index) {
                expected_string(&g_inputStrings[index]);
            }
            break;
        case VARIANT_LABEL:
            expected_string(&g_inputStrings[0]);
            expected_dword(g_nestedInput[0]);
            expected_string(&g_inputStrings[1]);
            break;
    }
}

static void reset_capture(int loading) {
    g_streamAt = 0;
    g_streamSize = loading ? g_expectedAt : 0;
    g_outputCount = 0;
    g_nestedCalls = 0;
    g_nestedOutput[0] = g_nestedOutput[1] = 0;
    g_streamFailed = 0;
    if (loading) {
        memcpy(g_stream, g_expected, g_expectedAt);
    } else {
        memset(g_stream, 0xcc, sizeof(g_stream));
    }
    memset(g_outputStrings, 0, sizeof(g_outputStrings));
}

static void check_loaded_strings(RecompCase* test, const Variant* variant) {
    recomp_check(test, g_outputCount, variant->strings);
    for (int index = 0; index < variant->strings; ++index) {
        recomp_check(test, g_outputStrings[index].length, g_inputStrings[index].length);
        recomp_check_mem(
            test,
            g_outputStrings[index].data,
            g_inputStrings[index].data,
            static_cast<unsigned int>(g_inputStrings[index].length)
        );
    }
}

static void run_variant(RecompCase* tests, const Variant* variant, unsigned int test) {
    unsigned char object[MAX_OBJECT];
    ArchiveState archive;
    RetailSerialize serialize = (RetailSerialize)RECOMP_RVA(variant->rva);

    prepare_inputs(test, variant->strings);
    build_expected(variant);

    memset(&archive, 0, sizeof(archive));
    archive.mode = 0;
    prepare_object(object, variant, 0);
    reset_capture(0);
    serialize(object, 0, &archive);
    recomp_check(tests + 0, g_streamFailed, 0);
    recomp_check(tests + 0, g_streamAt, g_expectedAt);
    recomp_check_mem(tests + 0, g_stream, g_expected, g_expectedAt);

    memset(&archive, 0, sizeof(archive));
    archive.mode = 1;
    prepare_object(object, variant, 1);
    reset_capture(1);
    serialize(object, 0, &archive);
    recomp_check(tests + 1, g_streamFailed, 0);
    recomp_check(tests + 1, g_streamAt, g_expectedAt);
    check_loaded_strings(tests + 1, variant);
    switch (variant->kind) {
        case VARIANT_WORD_BLOCK:
            recomp_check_mem(tests + 1, object + 0x1c, g_raw, 10);
            break;
        case VARIANT_RAW_BLOCK:
            recomp_check_mem(tests + 1, object + 0x20, g_raw, 0x48);
            break;
        case VARIANT_WORD_BLOCK_LABEL:
            recomp_check_mem(tests + 1, object + 0x1c, g_raw, 1);
            break;
        default:
            break;
    }
    recomp_check(
        tests + 2,
        g_nestedCalls,
        variant->kind == VARIANT_WORD_BLOCK  ? 2
        : variant->kind == VARIANT_RAW_BLOCK ? 0
                                             : 1
    );
    if (variant->kind != VARIANT_RAW_BLOCK) {
        recomp_check(tests + 2, g_nestedOutput[0], g_nestedInput[0]);
    }
    if (variant->kind == VARIANT_WORD_BLOCK) {
        recomp_check(tests + 2, g_nestedOutput[1], g_nestedInput[1]);
    }
}

static int patch_archive_primitives() {
    return recomp_patch_rel32(RVA_CSTRING_PUT_BYTE_SHORT, archive_put_byte)
           && recomp_patch_rel32(RVA_CSTRING_PUT_BYTE_WORD, archive_put_byte)
           && recomp_patch_rel32(RVA_CSTRING_PUT_WORD, archive_put_word)
           && recomp_patch_rel32(RVA_CSTRING_PUT_BYTE_DWORD, archive_put_byte)
           && recomp_patch_rel32(RVA_CSTRING_PUT_WORD_DWORD, archive_put_word)
           && recomp_patch_rel32(RVA_CSTRING_PUT_DWORD, archive_put_dword)
           && recomp_patch_rel32(RVA_CSTRING_WRITE, archive_write)
           && recomp_patch_rel32(RVA_CSTRING_GET_BUFFER, string_get_buffer)
           && recomp_patch_rel32(RVA_CSTRING_READ, archive_read)
           && recomp_patch_rel32(RVA_LENGTH_GET_BYTE, archive_get_byte)
           && recomp_patch_rel32(RVA_LENGTH_GET_WORD, archive_get_word)
           && recomp_patch_rel32(RVA_LENGTH_GET_DWORD, archive_get_dword)
           && recomp_patch_rel32(RVA_WORD_BLOCK_WRITE, archive_write)
           && recomp_patch_rel32(RVA_WORD_BLOCK_READ, archive_read)
           && recomp_patch_rel32(RVA_RAW_BLOCK_WRITE, archive_write)
           && recomp_patch_rel32(RVA_RAW_BLOCK_READ, archive_read)
           && recomp_patch_rel32(RVA_WORD_LABEL_WRITE, archive_write)
           && recomp_patch_rel32(RVA_WORD_LABEL_READ, archive_read);
}

int main(int argc, char** argv) {
    RecompCase tests[3];
    if (argc < 3) {
        fprintf(stderr, "usage: %s <ALLODS.EXE> <relocs.tsv>\n", argv[0]);
        return 1;
    }
    if (!recomp_map(argv[1], argv[2]) || !patch_archive_primitives()) {
        return 1;
    }
    g_nestedVtable[0] = 0;
    g_nestedVtable[1] = 0;
    g_nestedVtable[2] = (void*)nested_serialize;
    recomp_case(&tests[0], "TableLine store bytes");
    recomp_case(&tests[1], "TableLine load bytes/state");
    recomp_case(&tests[2], "TableLine nested dispatch");
    recomp_seed(RVA_WORD_BLOCK);
    for (unsigned int test = 0; test < 256; ++test) {
        for (unsigned int variant = 0; variant < sizeof(g_variants) / sizeof(g_variants[0]);
             ++variant) {
            run_variant(tests, &g_variants[variant], test);
        }
    }
    return recomp_report(tests, 3);
}

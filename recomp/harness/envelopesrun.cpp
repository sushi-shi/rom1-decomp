/* Execute the retail save reader and character packet reader with every
 * allocator/I/O/object edge replaced. Compare only their envelope grammar:
 * validation, field extents, byte counts, metadata, and compressed bytes. */

#include <MfcWin.h>

#include <Ints.h>

#include "recomp.h"

#define RVA_LOAD_SAVE 0x000cf1ee
#define RVA_SAVE_CONCAT_CALL 0x000cf22c
#define RVA_SAVE_LOG_PATH_CALL 0x000cf237
#define RVA_SAVE_FILE_CTOR_CALL 0x000cf242
#define RVA_SAVE_FILE_OPEN_CALL 0x000cf25e
#define RVA_SAVE_OPEN_FAIL_DTOR_CALL 0x000cf27b
#define RVA_SAVE_MAGIC_READ_CALL 0x000cf294
#define RVA_SAVE_INVALID_STRING_CALL 0x000cf2b0
#define RVA_SAVE_INVALID_LOG_CALL 0x000cf2bb
#define RVA_SAVE_INVALID_DTOR_CALL 0x000cf2d7
#define RVA_SAVE_SIZE_READ_CALL 0x000cf2f0
#define RVA_SAVE_VERSION_READ_CALL 0x000cf2fe
#define RVA_SAVE_OUTDATED_STRING_CALL 0x000cf31a
#define RVA_SAVE_OUTDATED_LOG_CALL 0x000cf325
#define RVA_SAVE_OUTDATED_DTOR_CALL 0x000cf341
#define RVA_SAVE_COMPRESSED_SIZE_READ_CALL 0x000cf35a
#define RVA_SAVE_ALLOC_CALL 0x000cf363
#define RVA_SAVE_PAYLOAD_READ_CALL 0x000cf379
#define RVA_SAVE_FILE_CLOSE_CALL 0x000cf381
#define RVA_SAVE_DECODE_CALL 0x000cf3a4
#define RVA_SAVE_PAYLOAD_FREE_CALL 0x000cf3c4
#define RVA_SAVE_MEMFILE_CTOR_CALL 0x000cf3e7
#define RVA_SAVE_ARCHIVE_CTOR_CALL 0x000cf403
#define RVA_SAVE_SCENARIO_CALL 0x000cf41d
#define RVA_SAVE_ARCHIVE_FLUSH_CALL 0x000cf47e
#define RVA_SAVE_MEMFILE_CLOSE_CALL 0x000cf486
#define RVA_SAVE_DECODED_FREE_CALL 0x000cf49b
#define RVA_SAVE_ARCHIVE_DTOR_CALL 0x000cf4b7
#define RVA_SAVE_MEMFILE_DTOR_CALL 0x000cf4c3
#define RVA_SAVE_FILE_DTOR_CALL 0x000cf4d2

#define RVA_LOAD_CHARACTER 0x000cf8b8
#define RVA_CHARACTER_METADATA_COPY_CALL 0x000cf8f0
#define RVA_CHARACTER_ALLOC_CALL 0x000cf90f
#define RVA_CHARACTER_PAYLOAD_COPY_CALL 0x000cf92c
#define RVA_CHARACTER_DECODE_CALL 0x000cf95b
#define RVA_CHARACTER_PAYLOAD_FREE_CALL 0x000cf981
#define RVA_CHARACTER_MEMFILE_CTOR_CALL 0x000cf9ad
#define RVA_CHARACTER_ARCHIVE_CTOR_CALL 0x000cf9cc
#define RVA_CHARACTER_DESERIALIZE_CALL 0x000cf9e1
#define RVA_CHARACTER_ARCHIVE_FLUSH_CALL 0x000cfa0a
#define RVA_CHARACTER_MEMFILE_CLOSE_CALL 0x000cfa15
#define RVA_CHARACTER_DECODED_FREE_CALL 0x000cfa2a
#define RVA_CHARACTER_ARCHIVE_DTOR_CALL 0x000cfa49
#define RVA_CHARACTER_MEMFILE_DTOR_CALL 0x000cfa5b

#define SAVE_MAGIC 0x26677341u
#define SAVE_VERSION 0x0bad0002u
#define MAX_COMPRESSED 1024
#define CHARACTER_PACKET_HEADER 14
#define CHARACTER_METADATA 16

typedef int(__fastcall* RetailLoadSave)(void*, void*, const char*);
typedef void*(__fastcall* RetailLoadCharacter)(void*, void*, void*, void*);

static const unsigned char* g_fileInput;
static unsigned int g_fileSize;
static unsigned int g_fileAt;
static unsigned int g_readCalls;
static unsigned int g_readSizes[5];
static int g_openResult;
static unsigned int g_decodeCalls;
static unsigned int g_decodeSize;
static unsigned char g_decodeBytes[MAX_COMPRESSED + 2];
static unsigned int g_metadataCopyCalls;
static unsigned int g_metadataCopySize;
static unsigned char g_metadataBytes[CHARACTER_METADATA];
static unsigned int g_payloadCopyCalls;
static unsigned int g_payloadCopySize;
static unsigned char g_payloadBytes[MAX_COMPRESSED + 2];

static void reset_capture(const unsigned char* input, unsigned int size) {
    g_fileInput = input;
    g_fileSize = size;
    g_fileAt = 0;
    g_readCalls = 0;
    memset(g_readSizes, 0, sizeof(g_readSizes));
    g_decodeCalls = 0;
    g_decodeSize = 0;
    memset(g_decodeBytes, 0xcc, sizeof(g_decodeBytes));
    g_metadataCopyCalls = 0;
    g_metadataCopySize = 0;
    memset(g_metadataBytes, 0xcc, sizeof(g_metadataBytes));
    g_payloadCopyCalls = 0;
    g_payloadCopySize = 0;
    memset(g_payloadBytes, 0xcc, sizeof(g_payloadBytes));
}

static void* __stdcall string_concat(void* result, const char*, const char*) {
    return result;
}

static void __cdecl log_message(void*) {}

static void __fastcall object_ctor(void*, void*) {}

static void __fastcall object_dtor(void*, void*) {}

static int __fastcall file_open(void*, void*, const char*, unsigned int, void*) {
    return g_openResult;
}

static unsigned int __fastcall file_read(void*, void*, void* output, unsigned int size) {
    unsigned int available = g_fileAt < g_fileSize ? g_fileSize - g_fileAt : 0;
    unsigned int copied = size < available ? size : available;
    if (g_readCalls < sizeof(g_readSizes) / sizeof(g_readSizes[0])) {
        g_readSizes[g_readCalls] = size;
    }
    ++g_readCalls;
    if (copied != 0) {
        memcpy(output, g_fileInput + g_fileAt, copied);
    }
    if (copied < size) {
        memset(static_cast<unsigned char*>(output) + copied, 0, size - copied);
    }
    g_fileAt += copied;
    return copied;
}

static void __fastcall object_close(void*, void*) {}

static void* __fastcall cstring_ctor(void* self, void*, const char*) {
    return self;
}

static void* __cdecl retail_alloc(unsigned int size) {
    return malloc(size != 0 ? size : 1);
}

static void __cdecl retail_free(void* allocation) {
    free(allocation);
}

static void __cdecl decode_word_rle(
    unsigned char* input,
    int size,
    unsigned short** output,
    int* wordCount
) {
    ++g_decodeCalls;
    g_decodeSize = static_cast<unsigned int>(size);
    if (size > 0 && static_cast<unsigned int>(size) <= sizeof(g_decodeBytes)) {
        memcpy(g_decodeBytes, input, size);
    }
    *output = static_cast<unsigned short*>(malloc(sizeof(unsigned short)));
    *wordCount = 0;
}

static void __fastcall memfile_ctor(void*, void*, void*, unsigned int, unsigned int) {}

static void __fastcall archive_ctor(void*, void*, void*, unsigned int, int, int) {}

static void __fastcall scenario_serialize(void*, void*, void*) {}

static void* __cdecl metadata_copy(void* destination, const void* source, unsigned int size) {
    ++g_metadataCopyCalls;
    g_metadataCopySize = size;
    if (size <= sizeof(g_metadataBytes)) {
        memcpy(g_metadataBytes, source, size);
    }
    return memcpy(destination, source, size);
}

static void* __cdecl payload_copy(void* destination, const void* source, unsigned int size) {
    ++g_payloadCopyCalls;
    g_payloadCopySize = size;
    if (size <= sizeof(g_payloadBytes)) {
        memcpy(g_payloadBytes, source, size);
    }
    return memcpy(destination, source, size);
}

static void __stdcall deserialize_character(void*, void** output) {
    *output = 0;
}

static void write_dword(unsigned char* output, unsigned int at, u32 value) {
    output[at + 0] = static_cast<unsigned char>(value);
    output[at + 1] = static_cast<unsigned char>(value >> 8);
    output[at + 2] = static_cast<unsigned char>(value >> 16);
    output[at + 3] = static_cast<unsigned char>(value >> 24);
}

static void run_save_case(
    RecompCase* tests,
    unsigned char* file,
    unsigned int compressedSize,
    int openResult
) {
    u32 magic = *reinterpret_cast<u32*>(file + 0);
    u32 version = *reinterpret_cast<u32*>(file + 8);
    int validMagic = magic == SAVE_MAGIC;
    int validVersion = static_cast<i32>(version) >= static_cast<i32>(SAVE_VERSION);
    int expectedResult = openResult && validMagic && validVersion ? 0 : 1;
    unsigned int expectedReads = !openResult ? 0 : !validMagic ? 1 : !validVersion ? 3 : 5;
    unsigned int expectedBytes = !openResult ? 0 : !validMagic ? 4 : !validVersion ? 12
                                                                          : 16 + compressedSize;
    unsigned char owner[4] = {0};

    g_openResult = openResult;
    reset_capture(file, 16 + compressedSize);
    int result = ((RetailLoadSave)RECOMP_RVA(RVA_LOAD_SAVE))(owner, 0, "fabricated.sav");

    recomp_check(tests + 0, result, expectedResult);
    recomp_check(tests + 0, g_readCalls, expectedReads);
    recomp_check(tests + 0, g_fileAt, expectedBytes);
    recomp_check(tests + 0, g_decodeCalls, expectedResult == 0 ? 1 : 0);
    if (expectedResult == 0) {
        recomp_check(tests + 0, g_readSizes[0], 4);
        recomp_check(tests + 0, g_readSizes[1], 4);
        recomp_check(tests + 0, g_readSizes[2], 4);
        recomp_check(tests + 0, g_readSizes[3], 4);
        recomp_check(tests + 0, g_readSizes[4], compressedSize);
        recomp_check(tests + 0, g_decodeSize, compressedSize);
        recomp_check_mem(tests + 1, g_decodeBytes, file + 16, compressedSize);
    }
}

static void run_character_case(
    RecompCase* tests,
    unsigned char* packet,
    unsigned int fileSize
) {
    unsigned char owner[4] = {0};
    unsigned char destination[4] = {0};
    unsigned int compressedSize = fileSize - CHARACTER_METADATA;

    reset_capture(0, 0);
    void* result = ((RetailLoadCharacter)RECOMP_RVA(RVA_LOAD_CHARACTER))(
        owner, 0, packet, destination
    );

    recomp_check(tests + 2, result == 0, 1);
    recomp_check(tests + 2, g_metadataCopyCalls, 1);
    recomp_check(tests + 2, g_metadataCopySize, CHARACTER_METADATA);
    recomp_check(tests + 2, g_payloadCopyCalls, 1);
    recomp_check(tests + 2, g_payloadCopySize, compressedSize);
    recomp_check(tests + 2, g_decodeCalls, 1);
    recomp_check(tests + 2, g_decodeSize, compressedSize);
    recomp_check_mem(tests + 3, g_metadataBytes, packet + CHARACTER_PACKET_HEADER, 16);
    recomp_check_mem(
        tests + 3,
        g_payloadBytes,
        packet + CHARACTER_PACKET_HEADER + CHARACTER_METADATA,
        compressedSize
    );
    recomp_check_mem(
        tests + 3,
        g_decodeBytes,
        packet + CHARACTER_PACKET_HEADER + CHARACTER_METADATA,
        compressedSize
    );
}

static int patch_save_reader() {
    return recomp_patch_rel32(RVA_SAVE_CONCAT_CALL, string_concat)
        && recomp_patch_rel32(RVA_SAVE_LOG_PATH_CALL, log_message)
        && recomp_patch_rel32(RVA_SAVE_FILE_CTOR_CALL, object_ctor)
        && recomp_patch_rel32(RVA_SAVE_FILE_OPEN_CALL, file_open)
        && recomp_patch_rel32(RVA_SAVE_OPEN_FAIL_DTOR_CALL, object_dtor)
        && recomp_patch_rel32(RVA_SAVE_MAGIC_READ_CALL, file_read)
        && recomp_patch_rel32(RVA_SAVE_INVALID_STRING_CALL, cstring_ctor)
        && recomp_patch_rel32(RVA_SAVE_INVALID_LOG_CALL, log_message)
        && recomp_patch_rel32(RVA_SAVE_INVALID_DTOR_CALL, object_dtor)
        && recomp_patch_rel32(RVA_SAVE_SIZE_READ_CALL, file_read)
        && recomp_patch_rel32(RVA_SAVE_VERSION_READ_CALL, file_read)
        && recomp_patch_rel32(RVA_SAVE_OUTDATED_STRING_CALL, cstring_ctor)
        && recomp_patch_rel32(RVA_SAVE_OUTDATED_LOG_CALL, log_message)
        && recomp_patch_rel32(RVA_SAVE_OUTDATED_DTOR_CALL, object_dtor)
        && recomp_patch_rel32(RVA_SAVE_COMPRESSED_SIZE_READ_CALL, file_read)
        && recomp_patch_rel32(RVA_SAVE_ALLOC_CALL, retail_alloc)
        && recomp_patch_rel32(RVA_SAVE_PAYLOAD_READ_CALL, file_read)
        && recomp_patch_rel32(RVA_SAVE_FILE_CLOSE_CALL, object_close)
        && recomp_patch_rel32(RVA_SAVE_DECODE_CALL, decode_word_rle)
        && recomp_patch_rel32(RVA_SAVE_PAYLOAD_FREE_CALL, retail_free)
        && recomp_patch_rel32(RVA_SAVE_MEMFILE_CTOR_CALL, memfile_ctor)
        && recomp_patch_rel32(RVA_SAVE_ARCHIVE_CTOR_CALL, archive_ctor)
        && recomp_patch_rel32(RVA_SAVE_SCENARIO_CALL, scenario_serialize)
        && recomp_patch_rel32(RVA_SAVE_ARCHIVE_FLUSH_CALL, object_close)
        && recomp_patch_rel32(RVA_SAVE_MEMFILE_CLOSE_CALL, object_close)
        && recomp_patch_rel32(RVA_SAVE_DECODED_FREE_CALL, retail_free)
        && recomp_patch_rel32(RVA_SAVE_ARCHIVE_DTOR_CALL, object_dtor)
        && recomp_patch_rel32(RVA_SAVE_MEMFILE_DTOR_CALL, object_dtor)
        && recomp_patch_rel32(RVA_SAVE_FILE_DTOR_CALL, object_dtor);
}

static int patch_character_reader() {
    return recomp_patch_rel32(RVA_CHARACTER_METADATA_COPY_CALL, metadata_copy)
        && recomp_patch_rel32(RVA_CHARACTER_ALLOC_CALL, retail_alloc)
        && recomp_patch_rel32(RVA_CHARACTER_PAYLOAD_COPY_CALL, payload_copy)
        && recomp_patch_rel32(RVA_CHARACTER_DECODE_CALL, decode_word_rle)
        && recomp_patch_rel32(RVA_CHARACTER_PAYLOAD_FREE_CALL, retail_free)
        && recomp_patch_rel32(RVA_CHARACTER_MEMFILE_CTOR_CALL, memfile_ctor)
        && recomp_patch_rel32(RVA_CHARACTER_ARCHIVE_CTOR_CALL, archive_ctor)
        && recomp_patch_rel32(RVA_CHARACTER_DESERIALIZE_CALL, deserialize_character)
        && recomp_patch_rel32(RVA_CHARACTER_ARCHIVE_FLUSH_CALL, object_close)
        && recomp_patch_rel32(RVA_CHARACTER_MEMFILE_CLOSE_CALL, object_close)
        && recomp_patch_rel32(RVA_CHARACTER_DECODED_FREE_CALL, retail_free)
        && recomp_patch_rel32(RVA_CHARACTER_ARCHIVE_DTOR_CALL, object_dtor)
        && recomp_patch_rel32(RVA_CHARACTER_MEMFILE_DTOR_CALL, object_dtor);
}

int main(int argc, char** argv) {
    RecompCase tests[4];
    unsigned char save[16 + MAX_COMPRESSED];
    unsigned char packet[CHARACTER_PACKET_HEADER + CHARACTER_METADATA + MAX_COMPRESSED + 2];

    if (argc < 3) {
        fprintf(stderr, "usage: %s <ALLODS.EXE> <relocs.tsv>\n", argv[0]);
        return 1;
    }
    if (!recomp_map(argv[1], argv[2]) || !patch_save_reader() || !patch_character_reader()) {
        return 1;
    }

    recomp_case(&tests[0], "save envelope control/extents");
    recomp_case(&tests[1], "save compressed payload");
    recomp_case(&tests[2], "character envelope extents");
    recomp_case(&tests[3], "character metadata/payload");
    recomp_seed(RVA_LOAD_SAVE ^ RVA_LOAD_CHARACTER);

    memset(save, 0, sizeof(save));
    write_dword(save, 0, SAVE_MAGIC);
    write_dword(save, 4, 0xdeadbeefu);
    write_dword(save, 8, SAVE_VERSION);
    write_dword(save, 12, 0);
    run_save_case(tests, save, 0, 0);
    run_save_case(tests, save, 0, 1);

    for (unsigned int test = 0; test < 2048; ++test) {
        unsigned int compressedSize = recomp_rand() % (MAX_COMPRESSED + 1);
        u32 magic = test % 11 == 0 ? recomp_rand() | 1u : SAVE_MAGIC;
        u32 version;
        switch (test % 7) {
            case 0:
                version = SAVE_VERSION - 1;
                break;
            case 1:
                version = 0x80000000u | recomp_rand();
                break;
            default:
                version = SAVE_VERSION + recomp_rand() % 0x10000u;
                break;
        }
        write_dword(save, 0, magic);
        write_dword(save, 4, recomp_rand());
        write_dword(save, 8, version);
        write_dword(save, 12, compressedSize);
        for (unsigned int index = 0; index < compressedSize; ++index) {
            save[16 + index] = static_cast<unsigned char>(recomp_rand());
        }
        run_save_case(tests, save, compressedSize, 1);

        unsigned int characterCompressed = (recomp_rand() % (MAX_COMPRESSED / 2 + 1)) * 2;
        unsigned int fileSize = CHARACTER_METADATA + characterCompressed;
        memset(packet, 0, CHARACTER_PACKET_HEADER);
        write_dword(packet, 10, fileSize / 2);
        for (unsigned int fileIndex = 0; fileIndex < fileSize; ++fileIndex) {
            packet[CHARACTER_PACKET_HEADER + fileIndex]
                = static_cast<unsigned char>(recomp_rand());
        }
        run_character_case(tests, packet, fileSize);
    }
    return recomp_report(tests, 4);
}

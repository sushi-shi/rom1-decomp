/* Execute retail CPixMap's P3/P6 loader and compare every observable parser
 * field and decoded pixel byte with the VC5 reconstruction. */

#include <MfcWin.h>

#define ROM1_PIXMAP_ORACLE
#include <Graphics/PixMap.h>
#undef ROM1_PIXMAP_ORACLE

#include "recomp.h"

#define RVA_LOAD_PPM 0x0008d430
#define RVA_PALETTE_FREE_CALL 0x0008d456
#define RVA_FOPEN_CALL 0x0008d471
#define RVA_FIRST_FGETS_CALL 0x0008d483
#define RVA_P6_HEADER_FGETS_CALL 0x0008d4a6
#define RVA_P6_SSCANF_CALL 0x0008d4c8
#define RVA_P6_MAX_FGETS_CALL 0x0008d4d8
#define RVA_P6_ALLOC_CALL 0x0008d4e9
#define RVA_P6_FREAD_CALL 0x0008d501
#define RVA_P3_HEADER_FGETS_CALL 0x0008d529
#define RVA_P3_SSCANF_CALL 0x0008d54b
#define RVA_P3_MAX_FGETS_CALL 0x0008d55b
#define RVA_P3_ALLOC_CALL 0x0008d56c
#define RVA_P3_FSCANF_CALL 0x0008d591
#define RVA_FCLOSE_CALL 0x0008d5b5

typedef BOOL(__fastcall* RetailLoadPpm)(void*, void*, CString&);

typedef char PixMapSizeMustBe36[(sizeof(CPixMap) == 36) ? 1 : -1];

struct CPixMapOracleAccess {
    static BOOL LoadPPM(CPixMap* pixMap, CString& fileName) {
        return pixMap->LoadPPM(fileName);
    }
};

struct CStringStorage {
    char* text;
};

static void* __cdecl retail_alloc(unsigned int size) {
    return malloc(size ? size : 1);
}

static void __cdecl retail_free(void* allocation) {
    free(allocation);
}

static FILE* __cdecl retail_fopen(const char* path, const char* mode) {
    return fopen(path, mode);
}

static char* __cdecl retail_fgets(char* line, int size, FILE* file) {
    return fgets(line, size, file);
}

static int __cdecl retail_sscanf(const char* line, const char* format, i32* first, i32* second) {
    return sscanf(line, format, first, second);
}

static size_t __cdecl retail_fread(void* output, size_t elementSize, size_t count, FILE* file) {
    return fread(output, elementSize, count, file);
}

static int __cdecl retail_fscanf(FILE* file, const char* format, i32* value) {
    return fscanf(file, format, value);
}

static int __cdecl retail_fclose(FILE* file) {
    return fclose(file);
}

static CString& string_view(CStringStorage* storage, char* text) {
    storage->text = text;
    return *reinterpret_cast<CString*>(storage);
}

static int write_case(const char* path, const unsigned char* bytes, size_t size) {
    FILE* file = fopen(path, "wb");
    if (file == 0) {
        return 0;
    }
    int ok = fwrite(bytes, 1, size, file) == size;
    fclose(file);
    return ok;
}

static void compare_objects(RecompCase* tests, CPixMap* ours, CPixMap* retail) {
    recomp_check(tests + 0, ours->m_fileType, retail->m_fileType);
    recomp_check(tests + 0, ours->m_bitCount, retail->m_bitCount);
    recomp_check(tests + 0, ours->m_redBits, retail->m_redBits);
    recomp_check(tests + 0, ours->m_greenBits, retail->m_greenBits);
    recomp_check(tests + 0, ours->m_blueBits, retail->m_blueBits);
    recomp_check(tests + 0, ours->m_width, retail->m_width);
    recomp_check(tests + 0, ours->m_height, retail->m_height);
    recomp_check(tests + 0, ours->m_palette == 0, retail->m_palette == 0);

    i32 size = ours->m_width * ours->m_height * 3;
    recomp_check(tests + 1, size, retail->m_width * retail->m_height * 3);
    recomp_check(tests + 1, ours->m_pixels != 0, retail->m_pixels != 0);
    if (size > 0 && ours->m_pixels != 0 && retail->m_pixels != 0) {
        for (i32 index = 0; index < size; ++index) {
            recomp_check(tests + 1, ours->m_pixels[index], retail->m_pixels[index]);
        }
    }
}

static int run_bytes(RecompCase* tests, const char* path, unsigned char* bytes, size_t size) {
    unsigned char oursStorage[sizeof(CPixMap)];
    unsigned char retailStorage[sizeof(CPixMap)];
    CStringStorage nameStorage;
    CString& name = string_view(&nameStorage, const_cast<char*>(path));
    CPixMap* ours = reinterpret_cast<CPixMap*>(oursStorage);
    CPixMap* retail = reinterpret_cast<CPixMap*>(retailStorage);

    if (!write_case(path, bytes, size)) {
        fprintf(stderr, "pixmap oracle: cannot write %s\n", path);
        return 0;
    }
    memset(oursStorage, 0, sizeof(oursStorage));
    memset(retailStorage, 0, sizeof(retailStorage));
    ours->m_fileType = PIXMAP_FILE_PPM;
    retail->m_fileType = PIXMAP_FILE_PPM;

    BOOL oursResult = CPixMapOracleAccess::LoadPPM(ours, name);
    BOOL retailResult = ((RetailLoadPpm)RECOMP_RVA(RVA_LOAD_PPM))(retail, 0, name);
    recomp_check(tests + 0, oursResult, retailResult);
    compare_objects(tests, ours, retail);

    ours->Empty();
    retail_free(retail->m_pixels);
    return 1;
}

static int append_text(unsigned char* out, int at, const char* text) {
    int size = strlen(text);
    memcpy(out + at, text, size);
    return at + size;
}

static int make_header(unsigned char* out, const char* magic, i32 width, i32 height, i32 test) {
    char line[64];
    int at = 0;
    at = append_text(out, at, magic);
    at = append_text(out, at, "\n");
    if ((test & 1) != 0) {
        at = append_text(out, at, "#retail skips only this full-line comment\n");
    }
    sprintf(line, "%d %d\n", width, height);
    at = append_text(out, at, line);
    at = append_text(out, at, (test & 2) != 0 ? "999\n" : "255\n");
    return at;
}

static int run_p6(RecompCase* tests, const char* path, i32 test) {
    unsigned char bytes[2048];
    i32 width = test % 9 + 1;
    i32 height = test / 9 % 7 + 1;
    i32 count = width * height * 3;
    int at = make_header(bytes, "P6", width, height, test);
    for (i32 index = 0; index < count; ++index) {
        bytes[at++] = static_cast<unsigned char>(recomp_rand());
    }
    return run_bytes(tests, path, bytes, at);
}

static int run_p3(RecompCase* tests, const char* path, i32 test) {
    unsigned char bytes[4096];
    char value[32];
    i32 width = test % 8 + 1;
    i32 height = test / 8 % 6 + 1;
    i32 count = width * height * 3;
    int at = make_header(bytes, "P3", width, height, test);
    for (i32 index = 0; index < count; ++index) {
        i32 component = static_cast<i32>(recomp_rand() % 4097) - 2048;
        sprintf(value, "%d%c", component, (index & 7) == 7 ? '\n' : ' ');
        at = append_text(bytes, at, value);
    }
    return run_bytes(tests, path, bytes, at);
}

int main(int argc, char** argv) {
    RecompCase tests[2];
    const char* path = "pixmap-oracle.ppm";

    if (argc < 3) {
        fprintf(stderr, "usage: %s <ALLODS.EXE> <relocs.tsv>\n", argv[0]);
        return 1;
    }
    if (!recomp_map(argv[1], argv[2]) || !recomp_patch_rel32(RVA_PALETTE_FREE_CALL, retail_free)
        || !recomp_patch_rel32(RVA_FOPEN_CALL, retail_fopen)
        || !recomp_patch_rel32(RVA_FIRST_FGETS_CALL, retail_fgets)
        || !recomp_patch_rel32(RVA_P6_HEADER_FGETS_CALL, retail_fgets)
        || !recomp_patch_rel32(RVA_P6_SSCANF_CALL, retail_sscanf)
        || !recomp_patch_rel32(RVA_P6_MAX_FGETS_CALL, retail_fgets)
        || !recomp_patch_rel32(RVA_P6_ALLOC_CALL, retail_alloc)
        || !recomp_patch_rel32(RVA_P6_FREAD_CALL, retail_fread)
        || !recomp_patch_rel32(RVA_P3_HEADER_FGETS_CALL, retail_fgets)
        || !recomp_patch_rel32(RVA_P3_SSCANF_CALL, retail_sscanf)
        || !recomp_patch_rel32(RVA_P3_MAX_FGETS_CALL, retail_fgets)
        || !recomp_patch_rel32(RVA_P3_ALLOC_CALL, retail_alloc)
        || !recomp_patch_rel32(RVA_P3_FSCANF_CALL, retail_fscanf)
        || !recomp_patch_rel32(RVA_FCLOSE_CALL, retail_fclose)) {
        return 1;
    }
    recomp_case(&tests[0], "PPM result and metadata");
    recomp_case(&tests[1], "PPM decoded pixel bytes");
    recomp_seed(0x0008d430u);

    for (i32 test = 0; test < 512; ++test) {
        if (!run_p6(tests, path, test) || !run_p3(tests, path, test)) {
            remove(path);
            return 1;
        }
    }
    remove(path);
    return recomp_report(tests, 2);
}

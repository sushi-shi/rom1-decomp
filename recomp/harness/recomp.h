#ifndef ROM1_RECOMP_H
#define ROM1_RECOMP_H

#include <windows.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RECOMP_IMAGE_BASE 0x00400000

static unsigned char* g_recomp_base = 0;

#define RECOMP_RVA(rva) ((void*)(g_recomp_base + (rva)))

static int recomp_apply_manifest(const char* path, long delta) {
    FILE* stream;
    char line[128];
    unsigned long rva;
    char kind[32];
    unsigned long applied = 0;

    if (delta == 0) {
        return 1;
    }
    stream = fopen(path, "rt");
    if (stream == 0) {
        fprintf(stderr, "recomp: cannot open relocation manifest %s\n", path);
        return 0;
    }
    while (fgets(line, sizeof(line), stream) != 0) {
        if (sscanf(line, "0x%lx\t%31s", &rva, kind) != 2) {
            continue;
        }
        if (strcmp(kind, "dir32") != 0) {
            fprintf(stderr, "recomp: unsupported relocation kind %s\n", kind);
            fclose(stream);
            return 0;
        }
        *(long*)(g_recomp_base + rva) += delta;
        ++applied;
    }
    fclose(stream);
    fprintf(stderr, "recomp: applied %lu reviewed DIR32 relocation(s)\n", applied);
    return applied != 0;
}

static int recomp_map(const char* imagePath, const char* relocPath) {
    FILE* stream;
    long fileSize;
    unsigned char* file;
    IMAGE_DOS_HEADER* dos;
    IMAGE_NT_HEADERS* nt;
    IMAGE_SECTION_HEADER* section;
    void* mapped;
    unsigned int index;
    unsigned long imageSize;

    stream = fopen(imagePath, "rb");
    if (stream == 0) {
        fprintf(stderr, "recomp: cannot open %s\n", imagePath);
        return 0;
    }
    fseek(stream, 0, SEEK_END);
    fileSize = ftell(stream);
    fseek(stream, 0, SEEK_SET);
    file = (unsigned char*)malloc((size_t)fileSize);
    if (file == 0 || fread(file, 1, (size_t)fileSize, stream) != (size_t)fileSize) {
        fprintf(stderr, "recomp: short read on %s\n", imagePath);
        fclose(stream);
        return 0;
    }
    fclose(stream);

    dos = (IMAGE_DOS_HEADER*)file;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        fprintf(stderr, "recomp: not an MZ image\n");
        free(file);
        return 0;
    }
    nt = (IMAGE_NT_HEADERS*)(file + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.ImageBase != RECOMP_IMAGE_BASE) {
        fprintf(stderr, "recomp: unexpected PE image or base\n");
        free(file);
        return 0;
    }

    imageSize = nt->OptionalHeader.SizeOfImage;
    mapped = VirtualAlloc(
        (void*)RECOMP_IMAGE_BASE,
        imageSize,
        MEM_RESERVE | MEM_COMMIT,
        PAGE_EXECUTE_READWRITE
    );
    if (mapped == 0) {
        mapped = VirtualAlloc(0, imageSize, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    }
    if (mapped == 0) {
        fprintf(stderr, "recomp: VirtualAlloc of %lu bytes failed\n", imageSize);
        free(file);
        return 0;
    }

    memcpy(mapped, file, nt->OptionalHeader.SizeOfHeaders);
    section = IMAGE_FIRST_SECTION(nt);
    for (index = 0; index < nt->FileHeader.NumberOfSections; ++index) {
        if (section[index].SizeOfRawData != 0) {
            memcpy(
                (unsigned char*)mapped + section[index].VirtualAddress,
                file + section[index].PointerToRawData,
                section[index].SizeOfRawData
            );
        }
    }
    free(file);

    g_recomp_base = (unsigned char*)mapped;
    if (mapped != (void*)RECOMP_IMAGE_BASE) {
        long delta = g_recomp_base - (unsigned char*)RECOMP_IMAGE_BASE;
        fprintf(stderr, "recomp: image at %p (relocated from %08x)\n", mapped, RECOMP_IMAGE_BASE);
        if (!recomp_apply_manifest(relocPath, delta)) {
            return 0;
        }
    }
    return 1;
}

static int recomp_patch_rel32(unsigned long callRva, void* target) {
    unsigned char* call = g_recomp_base + callRva;
    if (call[0] != 0xe8) {
        fprintf(stderr, "recomp: RVA %08lx is not a rel32 call\n", callRva);
        return 0;
    }
    *(long*)(call + 1) = (unsigned char*)target - (call + 5);
    return 1;
}

static unsigned int g_recomp_rng = 0x2545f491u;

static void recomp_seed(unsigned int seed) {
    g_recomp_rng = seed ? seed : 1u;
}

static unsigned int recomp_rand(void) {
    unsigned int value = g_recomp_rng;
    value ^= value << 13;
    value ^= value >> 17;
    value ^= value << 5;
    g_recomp_rng = value;
    return value;
}

typedef struct RecompCase {
    const char* name;
    unsigned long checked;
    unsigned long disagreed;
    unsigned int shown;
} RecompCase;

static void recomp_case(RecompCase* test, const char* name) {
    test->name = name;
    test->checked = 0;
    test->disagreed = 0;
    test->shown = 0;
}

static int recomp_check(RecompCase* test, int ours, int retail) {
    ++test->checked;
    if (ours == retail) {
        return 0;
    }
    ++test->disagreed;
    if (test->shown++ < 10) {
        fprintf(stderr, "  [%s] #%lu ours=%d retail=%d\n", test->name, test->checked, ours, retail);
    }
    return 1;
}

static int recomp_check_mem(RecompCase* test, const void* ours, const void* retail, size_t size) {
    ++test->checked;
    if (memcmp(ours, retail, size) == 0) {
        return 0;
    }
    ++test->disagreed;
    if (test->shown++ < 10) {
        size_t index;
        for (index = 0; index < size; ++index) {
            if (((const unsigned char*)ours)[index] != ((const unsigned char*)retail)[index]) {
                fprintf(
                    stderr,
                    "  [%s] #%lu byte %u: ours=%02x retail=%02x\n",
                    test->name,
                    test->checked,
                    (unsigned int)index,
                    ((const unsigned char*)ours)[index],
                    ((const unsigned char*)retail)[index]
                );
                break;
            }
        }
    }
    return 1;
}

static int recomp_report(RecompCase* tests, int count) {
    int index;
    int failed = 0;
    printf("\n%-40s %12s %12s\n", "CASE", "CHECKED", "DISAGREED");
    printf("------------------------------------------------------------------\n");
    for (index = 0; index < count; ++index) {
        printf(
            "%-40s %12lu %12lu%s\n",
            tests[index].name,
            tests[index].checked,
            tests[index].disagreed,
            tests[index].disagreed ? " <-- DISAGREE" : ""
        );
        if (tests[index].checked == 0 || tests[index].disagreed != 0) {
            failed = 1;
        }
    }
    printf(
        "\n%s\n",
        failed ? "VERDICT: retail and ours DISAGREE."
               : "VERDICT: retail and ours agree on every input."
    );
    return failed;
}

#endif // ROM1_RECOMP_H

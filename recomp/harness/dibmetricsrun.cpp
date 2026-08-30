/* Execute retail CDib's pure BMP/DIB layout methods and compare them with the
 * VC5 reconstruction. All headers and object storage are fabricated. */

#include <MfcWin.h>

#define ROM1_DIB_ORACLE
#include <Graphics/Dib.h>
#undef ROM1_DIB_ORACLE

#include "recomp.h"

#define RVA_GET_DIMENSIONS 0x0004afa0
#define RVA_COMPUTE_PALETTE_SIZE 0x0004b990
#define RVA_COMPUTE_METRICS 0x0004ba20

typedef void(__fastcall* RetailNoArgs)(void*, void*);
typedef void(__fastcall* RetailBitCount)(void*, void*, i32);

typedef char DibSizeMustBe56[(sizeof(CDib) == 56) ? 1 : -1];

struct CDibOracleAccess {
    static void ComputePaletteSize(CDib* dib, i32 bitCount) {
        dib->ComputePaletteSize(bitCount);
    }

    static void ComputeMetrics(CDib* dib) {
        dib->ComputeMetrics();
    }
};

static void retail_dimensions(void* dib, CSize* result) {
    void* function = RECOMP_RVA(RVA_GET_DIMENSIONS);

    __asm {
        mov ecx, dib
        push result
        call function
    }
}

static i32 known_bit_count(i32 index) {
    static const i32 counts[] = {1, 4, 8, 16, 24, 32, 2, 7};
    return counts[index & 7];
}

static void compare_dimensions(RecompCase* test) {
    unsigned char oursStorage[sizeof(CDib)];
    unsigned char retailStorage[sizeof(CDib)];
    CDib* ours = (CDib*)oursStorage;
    CDib* retail = (CDib*)retailStorage;
    BITMAPINFOHEADER info;
    CSize oursSize;
    CSize retailSize;
    i32 iteration;

    memset(oursStorage, 0, sizeof(oursStorage));
    memset(retailStorage, 0, sizeof(retailStorage));
    oursSize = ours->GetDimensions();
    retail_dimensions(retail, &retailSize);
    recomp_check(test, oursSize.cx, retailSize.cx);
    recomp_check(test, oursSize.cy, retailSize.cy);

    memset(&info, 0, sizeof(info));
    ours->m_lpBMIH = &info;
    retail->m_lpBMIH = &info;
    for (iteration = 0; iteration < 8192; ++iteration) {
        info.biWidth = (i32)recomp_rand();
        info.biHeight = (i32)recomp_rand();
        oursSize = ours->GetDimensions();
        retail_dimensions(retail, &retailSize);
        recomp_check(test, oursSize.cx, retailSize.cx);
        recomp_check(test, oursSize.cy, retailSize.cy);
    }
}

static void compare_palette_size(RecompCase* test) {
    unsigned char oursStorage[sizeof(CDib)];
    unsigned char retailStorage[sizeof(CDib)];
    CDib* ours = (CDib*)oursStorage;
    CDib* retail = (CDib*)retailStorage;
    BITMAPINFOHEADER info;
    i32 iteration;

    memset(&info, 0, sizeof(info));
    memset(oursStorage, 0, sizeof(oursStorage));
    memset(retailStorage, 0, sizeof(retailStorage));
    ours->m_lpBMIH = &info;
    retail->m_lpBMIH = &info;
    for (iteration = 0; iteration < 16384; ++iteration) {
        i32 bitCount = known_bit_count(iteration);
        i32 sentinel = (i32)recomp_rand();
        info.biClrUsed = (iteration & 3) == 0 ? recomp_rand() & 0x3ff : 0;
        ours->m_nColorTableEntries = sentinel;
        retail->m_nColorTableEntries = sentinel;
        CDibOracleAccess::ComputePaletteSize(ours, bitCount);
        ((RetailBitCount)RECOMP_RVA(RVA_COMPUTE_PALETTE_SIZE))(
            retail, 0, bitCount
        );
        recomp_check(
            test, ours->m_nColorTableEntries, retail->m_nColorTableEntries
        );
    }
}

static void compare_metrics(RecompCase* tests) {
    unsigned char oursStorage[sizeof(CDib)];
    unsigned char retailStorage[sizeof(CDib)];
    CDib* ours = (CDib*)oursStorage;
    CDib* retail = (CDib*)retailStorage;
    BITMAPINFOHEADER info;
    i32 iteration;

    memset(&info, 0, sizeof(info));
    memset(oursStorage, 0, sizeof(oursStorage));
    memset(retailStorage, 0, sizeof(retailStorage));
    ours->m_lpBMIH = &info;
    retail->m_lpBMIH = &info;
    for (iteration = 0; iteration < 32768; ++iteration) {
        info.biWidth = (i32)(recomp_rand() % 4096) + 1;
        info.biHeight = (i32)(recomp_rand() % 4096) + 1;
        info.biBitCount = (WORD)known_bit_count(iteration);
        info.biSizeImage = (iteration & 3) == 0 ? recomp_rand() & 0x00ffffff : 0;
        CDibOracleAccess::ComputeMetrics(ours);
        ((RetailNoArgs)RECOMP_RVA(RVA_COMPUTE_METRICS))(retail, 0);
        recomp_check(tests + 0, ours->m_dwSizeImage, retail->m_dwSizeImage);
        recomp_check(
            tests + 1,
            (LPBYTE)ours->m_lpvColorTable - (LPBYTE)&info,
            (LPBYTE)retail->m_lpvColorTable - (LPBYTE)&info
        );
    }
}

int main(int argc, char** argv) {
    RecompCase tests[4];

    if (argc < 3) {
        fprintf(stderr, "usage: %s <ALLODS.EXE> <relocs.tsv>\n", argv[0]);
        return 1;
    }
    if (!recomp_map(argv[1], argv[2])) {
        return 1;
    }
    recomp_case(&tests[0], "reported dimensions");
    recomp_case(&tests[1], "palette entry count");
    recomp_case(&tests[2], "pixel image byte count");
    recomp_case(&tests[3], "palette byte offset");
    recomp_seed(0x0004ba20u);

    compare_dimensions(&tests[0]);
    compare_palette_size(&tests[1]);
    compare_metrics(&tests[2]);
    return recomp_report(tests, 4);
}

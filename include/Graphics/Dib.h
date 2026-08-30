#ifndef ROM1_GRAPHICS_DIB_H
#define ROM1_GRAPHICS_DIB_H

#include <MfcWin.h>

#include <Enums.h>
#include <Ints.h>

GZ_ENUM_BEGIN(DibBitCount)
    DIB_BIT_COUNT_MONO = 1,
    DIB_BIT_COUNT_16_COLOR = 4,
    DIB_BIT_COUNT_256_COLOR = 8,
    DIB_BIT_COUNT_HIGH_COLOR = 16,
    DIB_BIT_COUNT_TRUE_COLOR = 24,
    DIB_BIT_COUNT_TRUE_COLOR_ALPHA = 32,
GZ_ENUM_END(DibBitCount)

GZ_ENUM_BEGIN(DibAllocation)
    DIB_ALLOC_NONE = 0,
    DIB_ALLOC_CRT = 1,
    DIB_ALLOC_GLOBAL = 2,
GZ_ENUM_END(DibAllocation)

GZ_ENUM_CONST_BEGIN(DibLayoutConstants)
    DIB_BITMAP_SIGNATURE = 0x4d42,
    DIB_FILE_AND_INFO_HEADER_BYTES = 54,
GZ_ENUM_CONST_END(DibLayoutConstants)

class CDib : public CObject {
#if defined(ROM1_DIB_ORACLE)
    friend struct CDibOracleAccess;
#endif

public:
    CSize GetDimensions();
    BOOL Read(CFile* file);
    BOOL Write(CFile* file);
    BOOL MakePalette();
    void Empty();

private:
    void DetachMapFile();
    void ComputePaletteSize(GZ_ENUM_PARAM(DibBitCount, i32) bitCount);
    void ComputeMetrics();

public:
    LPVOID m_lpvColorTable;
    HBITMAP m_hBitmap;
    LPBYTE m_lpImage;
    LPBITMAPINFOHEADER m_lpBMIH;
    HGLOBAL m_hGlobal;
    GZ_ENUM_STORAGE(DibAllocation, i32) m_nBmihAlloc;
    GZ_ENUM_STORAGE(DibAllocation, i32) m_nImageAlloc;
    DWORD m_dwSizeImage;
    i32 m_nColorTableEntries;
    HANDLE m_hFile;
    HANDLE m_hMap;
    LPVOID m_lpvFile;
    HPALETTE m_hPalette;
};

#endif // ROM1_GRAPHICS_DIB_H

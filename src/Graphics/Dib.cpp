#include <rva.h>

#include <Graphics/Dib.h>

RVA_COMPGEN(0x0004ad40, 0x57, ?CreateObject@CDib@@SGPAVCObject@@XZ)
RVA_COMPGEN(0x0004ada0, 0x6, ?GetRuntimeClass@CDib@@UBEPAUCRuntimeClass@@XZ)
RVA_DYNINIT(0x0004adb0, 0x5, _init_CDib)
RVA_DYNINIT(0x0004adc0, 0x10, _init_CDib)
RVA_COMPGEN(0x0004add0, 0x1d, ??5@YGAAVCArchive@@AAV0@AAPAVCDib@@@Z)
IMPLEMENT_SERIAL(CDib, CObject, 1)

RVA(0x0004adf0, 0x4f)
CDib::CDib() {
    m_hFile = 0;
    m_hBitmap = 0;
    m_hPalette = 0;
    m_nBmihAlloc = m_nImageAlloc = DIB_ALLOC_NONE;
    Empty();
}

RVA_COMPGEN(0x0004ae40, 0x1e, ??_GCDib@@UAEPAXI@Z)

RVA(0x0004af50, 0x46)
CDib::~CDib() {
    Empty();
}

// @dead-code
// Zero-ref: the retail accessor has no direct call, data, or vtable reference.
RVA(0x0004afa0, 0x2d)
CSize CDib::GetDimensions() {
    if (m_lpBMIH == 0) {
        return CSize(0, 0);
    }
    return CSize(m_lpBMIH->biWidth, m_lpBMIH->biHeight);
}

RVA(0x0004b360, 0x91)
BOOL CDib::MakePalette() {
    if (m_nColorTableEntries == 0) {
        return FALSE;
    }
    if (m_hPalette != 0) {
        ::DeleteObject(m_hPalette);
    }

    // byte-forced variable-length Win32 LOGPALETTE tail.
    LOGPALETTE* logicalPalette = reinterpret_cast<LOGPALETTE*>(
        new char[sizeof(LOGPALETTE) + (m_nColorTableEntries - 1) * sizeof(PALETTEENTRY)]
    );
    logicalPalette->palVersion = 0x0300;
    logicalPalette->palNumEntries = static_cast<WORD>(m_nColorTableEntries);
    // byte-evidenced DIB color-table overlay.
    RGBQUAD* colorTable = reinterpret_cast<RGBQUAD*>(m_lpvColorTable);
    for (i32 index = 0; index < m_nColorTableEntries; ++index) {
        logicalPalette->palPalEntry[index].peRed = colorTable->rgbRed;
        logicalPalette->palPalEntry[index].peGreen = colorTable->rgbGreen;
        logicalPalette->palPalEntry[index].peBlue = colorTable->rgbBlue;
        logicalPalette->palPalEntry[index].peFlags = 0;
        ++colorTable;
    }
    m_hPalette = ::CreatePalette(logicalPalette);
    delete[] reinterpret_cast<char*>(logicalPalette); // byte-forced allocation owner
    return TRUE;
}

RVA(0x0004b710, 0x140)
BOOL CDib::Read(CFile* file) {
    Empty();
    UINT count;
    i32 headerBytes;
    BITMAPFILEHEADER header;

    TRY {
        count = file->Read(&header, sizeof(BITMAPFILEHEADER));
        if (count != sizeof(BITMAPFILEHEADER)) {
            AfxMessageBox("read error 1");
            return FALSE;
        }
        if (header.bfType != DIB_BITMAP_SIGNATURE) {
            AfxMessageBox("Invalid bitmap file");
            return FALSE;
        }
        headerBytes = header.bfOffBits - sizeof(BITMAPFILEHEADER);
        // byte-forced ownership: retail allocates one raw header/palette block.
        m_lpBMIH = reinterpret_cast<LPBITMAPINFOHEADER>(new char[headerBytes]);
        m_nBmihAlloc = m_nImageAlloc = DIB_ALLOC_CRT;
        count = file->Read(m_lpBMIH, headerBytes);
        ComputeMetrics();
        m_lpImage = new BYTE[m_dwSizeImage];
        count = file->Read(m_lpImage, m_dwSizeImage);
    }
    CATCH(CException, exception) {
        AfxMessageBox("Read error 1");
        return FALSE;
    }
    END_CATCH
    ComputePaletteSize(m_lpBMIH->biBitCount);
    MakePalette();
    return TRUE;
}

RVA(0x0004b860, 0xf0)
BOOL CDib::Write(CFile* file) {
    BITMAPFILEHEADER header;

    header.bfType = DIB_BITMAP_SIGNATURE;
    header.bfSize =
        m_dwSizeImage + m_nColorTableEntries * sizeof(RGBQUAD) + DIB_FILE_AND_INFO_HEADER_BYTES;
    header.bfReserved1 = header.bfReserved2 = 0;
    header.bfOffBits = m_nColorTableEntries * sizeof(RGBQUAD) + DIB_FILE_AND_INFO_HEADER_BYTES;
    TRY {
        file->Write(&header, sizeof(BITMAPFILEHEADER));
        file->Write(m_lpBMIH, sizeof(BITMAPINFOHEADER) + sizeof(RGBQUAD) * m_nColorTableEntries);
        file->Write(m_lpImage, m_dwSizeImage);
    }
    CATCH(CException, exception) {
        AfxMessageBox("write error");
        return FALSE;
    }
    END_CATCH
    return TRUE;
}

RVA(0x0004b950, 0x38)
void CDib::Serialize(CArchive& archive) {
    archive.Flush();
    if (archive.IsStoring()) {
        Write(archive.GetFile());
    } else {
        Read(archive.GetFile());
    }
}

RVA(0x0004b990, 0x88)
void CDib::ComputePaletteSize(GZ_ENUM_PARAM(DibBitCount, i32) bitCount) {
    if (m_lpBMIH->biClrUsed == 0) {
        switch (bitCount) {
            case DIB_BIT_COUNT_MONO:
            case DIB_BIT_COUNT_16_COLOR:
            case DIB_BIT_COUNT_256_COLOR:
                m_nColorTableEntries = 1 << bitCount;
                break;
            case DIB_BIT_COUNT_HIGH_COLOR:
            case DIB_BIT_COUNT_TRUE_COLOR:
            case DIB_BIT_COUNT_TRUE_COLOR_ALPHA:
                m_nColorTableEntries = 0;
                break;
        }
    } else {
        m_nColorTableEntries = m_lpBMIH->biClrUsed;
    }
}

RVA(0x0004ba20, 0x39)
void CDib::ComputeMetrics() {
    m_dwSizeImage = m_lpBMIH->biSizeImage;
    if (m_dwSizeImage == 0) {
        u32 scanlineBytes = (static_cast<u32>(m_lpBMIH->biWidth) * m_lpBMIH->biBitCount) / 32;
        if ((static_cast<u32>(m_lpBMIH->biWidth) * m_lpBMIH->biBitCount) % 32 != 0) {
            ++scanlineBytes;
        }
        scanlineBytes *= 4;
        m_dwSizeImage = scanlineBytes * m_lpBMIH->biHeight;
    }
    // byte-evidenced overlay: the RGBQUAD table starts after BITMAPINFOHEADER.
    m_lpvColorTable = reinterpret_cast<LPBYTE>(m_lpBMIH) + sizeof(BITMAPINFOHEADER);
}

RVA(0x0004ba60, 0x92)
void CDib::Empty() {
    DetachMapFile();
    if (m_nBmihAlloc == DIB_ALLOC_CRT) {
        delete[] m_lpBMIH;
    } else if (m_nBmihAlloc == DIB_ALLOC_GLOBAL) {
        ::GlobalUnlock(m_hGlobal);
        ::GlobalFree(m_hGlobal);
    }
    if (m_nImageAlloc == DIB_ALLOC_CRT) {
        delete[] m_lpImage;
    }
    if (m_hPalette != 0) {
        ::DeleteObject(m_hPalette);
    }
    if (m_hBitmap != 0) {
        ::DeleteObject(m_hBitmap);
    }
    m_nBmihAlloc = m_nImageAlloc = DIB_ALLOC_NONE;
    m_hGlobal = 0;
    m_lpBMIH = 0;
    m_lpImage = 0;
    m_lpvColorTable = 0;
    m_nColorTableEntries = 0;
    m_dwSizeImage = 0;
    m_lpvFile = 0;
    m_hMap = 0;
    m_hFile = 0;
    m_hBitmap = 0;
    m_hPalette = 0;
}

RVA(0x0004bb00, 0x31)
void CDib::DetachMapFile() {
    if (m_hFile == 0) {
        return;
    }
    ::UnmapViewOfFile(m_lpvFile);
    ::CloseHandle(m_hMap);
    ::CloseHandle(m_hFile);
    m_hFile = 0;
}

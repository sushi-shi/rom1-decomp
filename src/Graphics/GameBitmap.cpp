#include <rva.h>

#include <Graphics/GameBitmap.h>

// These aligned byte fields describe the active 16-bit display-pixel layout.
// Their storage belongs to the display-configuration owner; this unit only
// consumes them while expanding pixels for a BMP file.
// clang-format off
DATA(0x001bcefc) extern BYTE g_bitmapRedShift;
DATA(0x001bcf00) extern BYTE g_bitmapGreenShift;
DATA(0x001bcf04) extern BYTE g_bitmapRedBits;
DATA(0x001bcf08) extern BYTE g_bitmapGreenBits;
DATA(0x001bcf0c) extern BYTE g_bitmapBlueBits;
DATA(0x001eb4cc) extern BYTE g_bitmapBlueShift;
DATA(0x001cd790) extern BYTE g_bitmapIoBuffer[0x16800];
// clang-format on

RVA(0x00029260, 0xab)
void ConvertBitmap16To24(const WORD* source, BYTE* destination, int pixelCount) {
    while (pixelCount > 0) {
        WORD pixel = *source++;
        BYTE red = static_cast<BYTE>((pixel >> g_bitmapRedShift) << (8 - g_bitmapRedBits));
        BYTE green = static_cast<BYTE>((pixel >> g_bitmapGreenShift) << (8 - g_bitmapGreenBits));
        BYTE blue = static_cast<BYTE>((pixel >> g_bitmapBlueShift) << (8 - g_bitmapBlueBits));
        *destination++ = blue;
        *destination++ = green;
        *destination++ = red;
        --pixelCount;
    }
}

RVA(0x000296f0, 0x12e)
void CBmp64k::WriteBmp(LPCSTR fileName, CGameBitmap* auxiliaryPlane) {
    CFile file;
    file.Open(fileName, CFile::modeCreate | CFile::modeWrite, NULL);

    BITMAPFILEHEADER fileHeader;
    BITMAPINFOHEADER infoHeader;
    infoHeader.biWidth = Width(0);
    infoHeader.biHeight = Height(0);
    file.Write(&fileHeader, sizeof(fileHeader));
    file.Write(&infoHeader, sizeof(infoHeader));

    int remainingBytes = infoHeader.biWidth * infoHeader.biHeight * 3;
    // byte-evidenced 8-byte dimension header followed by packed WORD pixels.
    const WORD* source = reinterpret_cast<const WORD*>(m_bitmapData + 8);
    while (remainingBytes > 0) {
        int writeBytes = remainingBytes > static_cast<int>(sizeof(g_bitmapIoBuffer))
                             ? static_cast<int>(sizeof(g_bitmapIoBuffer))
                             : remainingBytes;
        int pixelCount = writeBytes / 3;
        ConvertBitmap16To24(source, g_bitmapIoBuffer, pixelCount);
        file.Write(g_bitmapIoBuffer, writeBytes);
        remainingBytes -= writeBytes;
        source += pixelCount;
    }

    if (auxiliaryPlane != NULL) {
        file.Write(auxiliaryPlane->m_bitmapData + 8, infoHeader.biWidth * infoHeader.biHeight);
    }
    file.Close();
}

#ifndef ROM1_GRAPHICS_PIXMAP_H
#define ROM1_GRAPHICS_PIXMAP_H

#include <MfcWin.h>

#include <DirectX/DirectXException.h>
#include <Enums.h>
#include <Ints.h>

GZ_ENUM_BEGIN(PixMapFileType)
    PIXMAP_FILE_UNKNOWN = -1,
    PIXMAP_FILE_NONE = 0,
    PIXMAP_FILE_PPM = 1,
    PIXMAP_FILE_BMP = 2,
    PIXMAP_FILE_PCX = 3,
GZ_ENUM_END(PixMapFileType)

class CPixMap {
#if defined(ROM1_PIXMAP_ORACLE)
    friend struct CPixMapOracleAccess;
#endif

public:
    CPixMap();
    CPixMap(CString& fileName);
    ~CPixMap();

    void Empty();
    void Load(CString& fileName);

private:
    void FindFileType(CString& fileName);
    BOOL LoadPPM(CString& fileName);
    BOOL LoadPCX(CString& fileName);
    BOOL LoadBMP(CString& fileName);

public:
    GZ_ENUM_STORAGE(PixMapFileType, i32) m_fileType;
    i32 m_bitCount;
    i32 m_redBits;
    i32 m_greenBits;
    i32 m_blueBits;
    u8* m_palette;
    i32 m_width;
    i32 m_height;
    u8* m_pixels;
};

#endif // ROM1_GRAPHICS_PIXMAP_H

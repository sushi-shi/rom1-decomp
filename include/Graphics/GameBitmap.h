#ifndef ROM1_GRAPHICS_GAMEBITMAP_H
#define ROM1_GRAPHICS_GAMEBITMAP_H

#include <MfcWin.h>

class CGameBitmap : public CObject {
public:
    virtual void BitmapOperation5() = 0;
    virtual void BitmapOperation6() = 0;
    virtual void BitmapOperation7() = 0;
    virtual int Width(int level) = 0;
    virtual int Height(int level) = 0;

    BYTE m_reserved04[8];
    void* m_levels;
    BYTE* m_bitmapData;
    BYTE m_reserved14[0x10];
};

class CBmp64k : public CGameBitmap {
public:
    void WriteBmp(LPCSTR fileName, CGameBitmap* auxiliaryPlane);
};

#endif // ROM1_GRAPHICS_GAMEBITMAP_H

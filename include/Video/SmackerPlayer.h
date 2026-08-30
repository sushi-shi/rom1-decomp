#ifndef ROM1_VIDEO_SMACKERPLAYER_H
#define ROM1_VIDEO_SMACKERPLAYER_H

#include <Enums.h>
#include <Ints.h>

#include <smack.h>

struct IDirectDrawSurface;

GZ_ENUM_CONST_BEGIN(SmackerPixelFormat)
    SMACKER_PIXEL_BITS_INDEXED = 8,
    SMACKER_PIXEL_R_MASK_565 = 0xf800,
    SMACKER_PIXEL_G_MASK_565 = 0x07e0,
    SMACKER_PIXEL_B_MASK_565 = 0x001f,
    SMACKER_PIXEL_R_MASK_555 = 0x7c00,
    SMACKER_PIXEL_G_MASK_555 = 0x03e0,
    SMACKER_PIXEL_B_MASK_555 = 0x001f,
GZ_ENUM_CONST_END(SmackerPixelFormat)

struct CSmackerBuffers {
    u8* m_first;
    i32 m_firstCount;
    i32 m_firstCapacity;
    u8* m_second;
    i32 m_secondCount;
    i32 m_secondCapacity;
    u8* m_third;

    CSmackerBuffers();
    ~CSmackerBuffers();
};

struct SmackerSize {
    i32 cx;
    i32 cy;

    SmackerSize(i32 x, i32 y) : cx(x), cy(y) {}
};

class CSmackerPlayer {
public:
    Smack* m_movie;            // 0x000
    u32 m_blitFlags;           // 0x004
    SmackBuf* m_buffer;        // 0x008
    HSMACKBLIT m_blitter;      // 0x00c
    CSmackerBuffers m_buffers; // 0x010
    u8 m_reserved2c[0x34 - 0x2c];
    i32 m_state; // 0x034
    u8 m_statePadding[0x33c - 0x38];
    float m_scale;    // 0x33c
    i32 m_centerX;    // 0x340
    i32 m_centerY;    // 0x344
    i32 m_destX;      // 0x348
    i32 m_destY;      // 0x34c
    i32 m_destWidth;  // 0x350
    i32 m_destHeight; // 0x354
    i32 m_sourceX;    // 0x358
    i32 m_sourceY;    // 0x35c
    i32 m_panX;       // 0x360
    i32 m_panY;       // 0x364
    b32 m_halfSize;   // 0x368
    void* m_window;   // 0x36c
    void* m_surface;  // 0x370

    CSmackerPlayer();
    SmackerSize GetMovieSize() const;
    u32 GetBufferFormat(IDirectDrawSurface* surface);
    void SetDestinationSize(i32 width, i32 height);
    void ApplyPan();
};

#endif // ROM1_VIDEO_SMACKERPLAYER_H

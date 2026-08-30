#include <rva.h>

#include <Video/SmackerPlayer.h>

#include <ddraw.h>

RVA(0x000ae650, 0x19)
CSmackerBuffers::CSmackerBuffers()
    : m_first(0),
      m_firstCount(0),
      m_firstCapacity(0),
      m_second(0),
      m_secondCount(0),
      m_secondCapacity(0),
      m_third(0) {}

RVA(0x000ae670, 0x46)
CSmackerBuffers::~CSmackerBuffers() {
    if (m_first != 0) {
        delete m_first;
    }
    m_first = 0;
    if (m_second != 0) {
        delete m_second;
    }
    m_second = 0;
    m_firstCapacity = 0;
    if (m_third != 0) {
        delete m_third;
    }
    m_third = 0;
    m_secondCapacity = 0;
}

RVA(0x000ae6c0, 0xb4)
CSmackerPlayer::CSmackerPlayer() {
    volatile CSmackerPlayer* self = this;
    self->m_destY = 0;
    self->m_destX = 0;
    self->m_destHeight = 0;
    self->m_destWidth = 0;
    self->m_halfSize = 0;
    m_movie = 0;
    m_buffer = 0;
    m_blitter = 0;
    m_state = 0;
    m_centerY = 0;
    m_centerX = 0;
    m_scale = 1.0f;
    m_sourceY = 0;
    m_sourceX = 0;
    m_panY = 0;
    m_panX = 0;
    m_surface = 0;
    m_blitFlags = 0;
    m_window = 0;
    SmackUseMMX(1);
    SmackSoundUseDirectSound(0);
}

RVA(0x000ae7f0, 0x9a)
u32 CSmackerPlayer::GetBufferFormat(IDirectDrawSurface* surface) {
    DDPIXELFORMAT format;
    format.dwSize = sizeof(format);
    format.dwFlags = DDPF_RGB;
    surface->GetPixelFormat(&format);

    if (format.dwRGBBitCount == SMACKER_PIXEL_BITS_INDEXED) {
        return 0;
    }
    if (format.dwRBitMask == SMACKER_PIXEL_R_MASK_565
        && format.dwGBitMask == SMACKER_PIXEL_G_MASK_565
        && format.dwBBitMask == SMACKER_PIXEL_B_MASK_565) {
        return SMACKBUFFER565;
    }
    if (format.dwRBitMask == SMACKER_PIXEL_R_MASK_555
        && format.dwGBitMask == SMACKER_PIXEL_G_MASK_555
        && format.dwBBitMask == SMACKER_PIXEL_B_MASK_555) {
        return SMACKBUFFER555;
    }

    MessageBoxA(
        static_cast<HWND>(m_window),
        DATA_COMPGEN(0x001c086c, "Unsupported pixel format."), DATA_COMPGEN(0x001c0888, "Smacker Error"), MB_ICONERROR);
    return 0;
}

RVA(0x000aedd0, 0x2c)
SmackerSize CSmackerPlayer::GetMovieSize() const {
    if (m_movie != 0) {
        return SmackerSize(m_movie->Width, m_movie->Height);
    }
    return SmackerSize(0, 0);
}

RVA(0x000aee00, 0x17)
void CSmackerPlayer::SetDestinationSize(i32 width, i32 height) {
    m_destWidth = width;
    m_destHeight = height;
}

RVA(0x000af2c0, 0x29)
void CSmackerPlayer::ApplyPan() {
    m_destX += m_panX;
    m_destY += m_panY;
}

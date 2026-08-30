#include <rva.h>

#include <Graphics/PixMap.h>

#include <stdio.h>

RVA(0x0008d1e0, 0x23)
CPixMap::CPixMap() {
    m_fileType = PIXMAP_FILE_UNKNOWN;
    m_bitCount = 0;
    m_blueBits = 0;
    m_greenBits = 0;
    m_redBits = 0;
    m_height = 0;
    m_width = 0;
    m_pixels = 0;
    m_palette = 0;
}

// @dead-code: retained because FPO gives an exact standalone constructor.
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x0008d210, 0x33)
CPixMap::CPixMap(CString& fileName) {
    m_bitCount = 0;
    m_blueBits = 0;
    m_greenBits = 0;
    m_redBits = 0;
    m_height = 0;
    m_width = 0;
    m_pixels = 0;
    m_palette = 0;
    m_fileType = PIXMAP_FILE_UNKNOWN;
    Load(fileName);
}

RVA(0x0008d250, 0x5)
CPixMap::~CPixMap() {
    Empty();
}

RVA(0x0008d260, 0x47)
void CPixMap::Empty() {
    m_fileType = PIXMAP_FILE_UNKNOWN;
    m_bitCount = 0;
    m_blueBits = 0;
    m_greenBits = 0;
    m_redBits = 0;
    m_height = 0;
    m_width = 0;
    if (m_pixels != 0) {
        delete[] m_pixels;
    }
    if (m_palette != 0) {
        delete[] m_palette;
    }
    m_pixels = 0;
    m_palette = 0;
}

RVA(0x0008d2b0, 0x73)
void CPixMap::FindFileType(CString& fileName) {
    m_fileType = PIXMAP_FILE_UNKNOWN;
    if (fileName.Find(".pcx") != -1) {
        m_fileType = PIXMAP_FILE_PCX;
        return;
    }
    if (fileName.Find(".ppm") != -1) {
        m_fileType = PIXMAP_FILE_PPM;
        return;
    }
    if (fileName.Find(".bmp") != -1 || fileName.Find(".dib") != -1) {
        m_fileType = PIXMAP_FILE_BMP;
    }
}

RVA(0x0008d330, 0xfc)
void CPixMap::Load(CString& fileName) {
    Empty();
    FindFileType(fileName);
    switch (m_fileType) {
        case PIXMAP_FILE_PPM:
            LoadPPM(fileName);
            return;
        case PIXMAP_FILE_PCX:
            LoadPCX(fileName);
            return;
        case PIXMAP_FILE_BMP:
            LoadBMP(fileName);
            return;
        case PIXMAP_FILE_UNKNOWN:
            throw new CDirectXException("Unknown file type in CPixMap::Load.");
        case PIXMAP_FILE_NONE:
            return;
    }
}

RVA(0x0008d430, 0x19c)
BOOL CPixMap::LoadPPM(CString& fileName) {
    char line[100];

    m_blueBits = 8;
    m_greenBits = 8;
    m_redBits = 8;
    m_bitCount = 24;
    if (m_palette != 0) {
        delete[] m_palette;
        m_palette = 0;
    }

    FILE* file = fopen(fileName, "rb");
    fgets(line, sizeof(line), file);
    if (line[0] == 'P' && line[1] == '6') {
        do {
            fgets(line, sizeof(line), file);
        } while (line[0] == '#');
        sscanf(line, "%d %d", &m_width, &m_height);
        fgets(line, sizeof(line), file);
        m_pixels = new u8[m_width * m_height * 3];
        fread(m_pixels, 1, m_width * m_height * 3, file);
    } else if (line[0] == 'P' && line[1] == '3') {
        do {
            fgets(line, sizeof(line), file);
        } while (line[0] == '#');
        sscanf(line, "%d %d", &m_width, &m_height);
        fgets(line, sizeof(line), file);
        m_pixels = new u8[m_width * m_height * 3];
        for (i32 pixel = 0; pixel < m_width * m_height * 3; ++pixel) {
            i32 value;
            fscanf(file, "%d", &value);
            m_pixels[pixel] = static_cast<u8>(value);
        }
    }
    fclose(file);
    return TRUE;
}

RVA(0x0008d5d0, 0x8)
BOOL CPixMap::LoadPCX(CString&) {
    return TRUE;
}

RVA(0x0008d5e0, 0x8)
BOOL CPixMap::LoadBMP(CString&) {
    return TRUE;
}

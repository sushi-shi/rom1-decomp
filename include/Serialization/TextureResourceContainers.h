#ifndef ROM1_SERIALIZATION_TEXTURERESOURCECONTAINERS_H
#define ROM1_SERIALIZATION_TEXTURERESOURCECONTAINERS_H

#include <MfcNoInline.h>

#include <afxtempl.h>
#include <ddraw.h>

// These six records belong to the global texture/resource owner constructed at
// 0x0982a0.  Retail field-use and the collection implementations preserve their
// complete extents.  Only the two non-trivial tails below survive strongly
// enough to name as fields; the remaining bytes stay opaque until their owner
// methods are reconstructed.
// @identity-TODO: recover the original record and owner class names.
struct CTextureCommandRecord {
    BYTE m_state[0x20];
};

struct CTextureSpanRecord {
    BYTE m_state[0x08];
};

class CTextureRuntimeObject;

struct CTextureRuntimeObjectReference {
    CTextureRuntimeObject* m_value;
};

class CTextureDescriptorRecord {
public:
    CTextureDescriptorRecord() : m_object(NULL) {}

private:
    BYTE m_state[0x78];
    CTextureRuntimeObject* m_object;
};

class CTextureTableRecord {
public:
    CTextureTableRecord();

private:
    BYTE m_state[0x12c];
    DWORD m_tail[4];
};

struct CTextureBlockRecord {
    BYTE m_state[0x80];
};

// Map nodes are constructed with two null DirectDraw references, a null
// scalar, and the exact retail fallback texture name.  Destruction releases
// both COM references through IUnknown slot 2.
class CTextureResourceRecord {
public:
    CTextureResourceRecord() {
        m_surface = NULL;
        m_palette = NULL;
        m_flags = 0;
        m_name = "Checker.ppm";
    }
    ~CTextureResourceRecord() {
        if (m_surface != NULL) {
            m_surface->Release();
            m_surface = NULL;
        }
        if (m_palette != NULL) {
            m_palette->Release();
            m_palette = NULL;
        }
        m_flags = 0;
    }

private:
    IDirectDrawSurface* m_surface;
    IDirectDrawPalette* m_palette;
    DWORD m_flags;
    CString m_name;
};

// The second map's value owns one DirectDraw reference plus one scalar.  Its
// key is a DWORD; retail's MFC HashKey path shifts the key by four before the
// bucket modulus, just as the pinned header specifies.
class CTextureLookupRecord {
public:
    CTextureLookupRecord() : m_surface(NULL), m_value(0) {}
    ~CTextureLookupRecord() {
        if (m_surface != NULL) {
            m_surface->Release();
            m_surface = NULL;
        }
        m_value = 0;
    }

private:
    IDirectDrawSurface* m_surface;
    DWORD m_value;
};

typedef CArray<CTextureCommandRecord, CTextureCommandRecord&> CTextureCommandArray;
typedef CArray<CTextureSpanRecord, CTextureSpanRecord&> CTextureSpanArray;
typedef CArray<CTextureRuntimeObjectReference, CTextureRuntimeObjectReference&>
    CTextureRuntimeObjectArray;
typedef CArray<CTextureDescriptorRecord, CTextureDescriptorRecord&> CTextureDescriptorArray;
typedef CArray<CTextureTableRecord, CTextureTableRecord&> CTextureTableArray;
typedef CArray<CTextureBlockRecord, CTextureBlockRecord&> CTextureBlockArray;
typedef CMap<DWORD, DWORD&, CTextureResourceRecord, CTextureResourceRecord&> CTextureResourceMap;
typedef CMap<DWORD, DWORD&, CTextureLookupRecord, CTextureLookupRecord&> CTextureLookupMap;

#endif // ROM1_SERIALIZATION_TEXTURERESOURCECONTAINERS_H

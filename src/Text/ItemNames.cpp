#include <rva.h>

#include <Text/ItemNames.h>

#include <stdlib.h>
#include <string.h>

RVA(0x00038850, 0x46)
CTextBlock::~CTextBlock() {
    Release();
}

RVA_COMPGEN(0x000388a0, 0x1e, ??_GCTextBlock@@UAEPAXI@Z)

RVA_DYNINIT(0x00067fa0, 0xa, g_itemNameText)
RVA_DYNINIT(0x00067fc0, 0xa, g_itemNameText)
DATA(0x001eb308)
CTextBlock g_itemNameText;

RVA_DYNINIT(0x000681a0, 0xa, g_textLines)
RVA_DYNINIT(0x000681c0, 0xa, g_textLines)
DATA(0x001eb328)
CTextPointerVector g_textLines;

RVA_DYNINIT(0x000682a0, 0xd, g_itemNames)
RVA_DYNINIT(0x000682c0, 0xa, g_itemNames)
DATA(0x001eb368)
CMapWordToPtr g_itemNames(10);

RVA(0x00068490, 0xcf)
void LoadItemNames() {
    CResourceFile file;
    file.Open("main\\text\\itemname.bin", 0, 0);

    i32 itemCount = file.GetLength() >> 1;
    i32 byteCount = itemCount * sizeof(u16);
    u16* itemIds = static_cast<u16*>(malloc(byteCount));
    file.Read(itemIds, byteCount);
    file.Close();

    for (i32 index = 0; index < itemCount; ++index) {
        g_itemNames[itemIds[index]] = g_itemNameText[index];
    }
    delete itemIds;
}

RVA(0x00068640, 0x14)
CTextBlock::CTextBlock() {
    m_allocation = 0;
    m_count = 0;
    m_firstIndex = 0;
}

RVA(0x00068660, 0x229)
void CTextBlock::Load(const char* resourcePath) {
    CResourceFile file;
    file.Open(resourcePath, 0, 0);
    i32 length = file.GetLength();
    m_allocation = static_cast<char*>(malloc(length));
    file.Read(m_allocation, length);
    file.Close();

    char* line = m_allocation;
    m_count = 0;
    m_firstIndex = g_textLines.GetSize();
    do {
        g_textLines.Add(line);
        while (*line != '\r') {
            ++line;
        }
        *line = '\0';
        line += 2;
        ++m_count;
    } while (line < m_allocation + length);
}

RVA(0x00068890, 0x65)
void CTextBlock::Release() {
    if (m_allocation != 0) {
        i32 first = 0;
        while (g_textLines[first] != m_allocation) {
            ++first;
        }
        g_textLines.RemoveAt(first, m_count);
        delete m_allocation;
        m_allocation = 0;
    }
}

RVA(0x00068900, 0x15)
char* CTextBlock::operator[](i32 index) {
    return static_cast<char*>(g_textLines[m_firstIndex + index]);
}

RVA(0x00069310, 0x17)
CTextPointerVector::CTextPointerVector() {
    m_data = 0;
    m_size = m_maxSize = m_growBy = 0;
}

RVA(0x00069330, 0x51)
CTextPointerVector::~CTextPointerVector() {
    if (m_data != 0) {
        delete[] reinterpret_cast<BYTE*>(m_data); // byte-evidenced allocation owner
    }
}

RVA(0x00069390, 0x188)
void CTextPointerVector::Serialize(CArchive& archive) {
    if (archive.IsStoring()) {
        archive.WriteCount(m_size);
    } else {
        SetSize(archive.ReadCount());
    }

    if (archive.IsStoring()) {
        archive.Write(m_data, m_size * sizeof(void*));
    } else {
        archive.Read(m_data, m_size * sizeof(void*));
    }
}

RVA_COMPGEN(0x00069520, 0x1e, ??_GCTextPointerVector@@UAEPAXI@Z)

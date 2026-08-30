#include <rva.h>

#include <Graphics/RadialOffsetTable.h>

// @dead-code
// Zero-ref: the retail writer has no direct call, data, or vtable reference.
RVA(0x000855d0, 0xb7)
void CRadialOffsetTable::Save(CString& fileName) {
    CFile file(fileName, CFile::modeWrite);

    file.Write(&m_outerRadius, sizeof(m_outerRadius));
    file.Write(&m_size, sizeof(m_size));
    file.Write(&m_innerRadius, sizeof(m_innerRadius));

    for (i32 row = 0; row < m_size; ++row) {
        for (i32 column = 0; column < m_size; ++column) {
            file.Write(&m_offsets[row][column], sizeof(CRadialOffset));
        }
    }
}

// @dead-code
// Zero-ref: the retail reader has no direct call, data, or vtable reference.
RVA(0x00085690, 0xea)
void CRadialOffsetTable::Load(CString& fileName) {
    CFile file(fileName, CFile::modeRead);

    file.Read(&m_outerRadius, sizeof(m_outerRadius));
    file.Read(&m_size, sizeof(m_size));
    file.Read(&m_innerRadius, sizeof(m_innerRadius));

    i32 allocationSize = m_size;
    m_offsets = new CRadialOffset*[allocationSize];
    for (i32 allocationRow = 0; allocationRow < allocationSize; ++allocationRow) {
        m_offsets[allocationRow] = new CRadialOffset[allocationSize];
    }

    for (i32 row = 0; row < m_size; ++row) {
        for (i32 column = 0; column < m_size; ++column) {
            file.Read(&m_offsets[row][column], sizeof(CRadialOffset));
        }
    }
}

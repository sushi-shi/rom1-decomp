#ifndef ROM1_GRAPHICS_RADIALOFFSETTABLE_H
#define ROM1_GRAPHICS_RADIALOFFSETTABLE_H

#include <MfcWin.h>

#include <Ints.h>

struct CRadialOffset {
    i16 x;
    i16 y;
};

class CRadialOffsetTable {
public:
    void Save(CString& fileName);
    void Load(CString& fileName);

private:
    CRadialOffset** m_offsets;
    i32 m_outerRadius;
    i32 m_innerRadius;
    i32 m_size;
};

#endif // ROM1_GRAPHICS_RADIALOFFSETTABLE_H

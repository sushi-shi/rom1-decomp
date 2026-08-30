#ifndef ROM1_TEXT_ITEMNAMES_H
#define ROM1_TEXT_ITEMNAMES_H

#include <Mfc.h>

#include <Ints.h>
#include <Io/ResourceFile.h>

#include <string.h>

// Game-owned pointer vector. Its layout and serializer deliberately mirror
// the contemporary MFC pointer array, but its retail vtable inherits CObject's
// runtime-class slot rather than CPtrArray's, proving that it is a distinct
// class. The original class name has not survived.
class CTextPointerVector : public CObject {
public:
    CTextPointerVector();
    virtual ~CTextPointerVector();
    virtual void Serialize(CArchive& archive);

    void* operator[](i32 index) const {
        return m_data[index];
    }

    void RemoveAt(i32 index, i32 count) {
        void** destination = &m_data[index];
        i32 moveCount = m_size - (index + count);
        if (moveCount != 0) {
            memcpy(destination, destination + count, moveCount * sizeof(void*));
        }
        m_size -= count;
    }

    i32 Add(void* value);
    i32 GetSize() const;

private:
    void SetSize(i32 newSize) {
        i32 growBy;
        i32 newMaxSize;
        void** newData;

        if (newSize == 0) {
            if (m_data != 0) {
                delete[] reinterpret_cast<BYTE*>(m_data); // byte-evidenced allocation owner
                m_data = 0;
            }
            m_size = m_maxSize = 0;
        } else if (m_data == 0) {
            // byte-evidenced storage
            m_data = reinterpret_cast<void**>(new BYTE[newSize * sizeof(void*)]);
            memset(m_data, 0, newSize * sizeof(void*));
            m_size = m_maxSize = newSize;
        } else if (newSize <= m_maxSize) {
            if (newSize > m_size) {
                for (i32 index = m_size; index < newSize; ++index) {
                    m_data[index] = 0;
                }
            }
            m_size = newSize;
        } else {
            growBy = m_growBy;
            if (growBy == 0) {
                growBy = m_size / 8;
                if (growBy < 4) {
                    growBy = 4;
                } else if (growBy > 1024) {
                    growBy = 1024;
                }
            }
            newMaxSize = m_maxSize + growBy;
            if (newSize >= newMaxSize) {
                newMaxSize = newSize;
            }
            // byte-evidenced storage
            newData = reinterpret_cast<void**>(new BYTE[newMaxSize * sizeof(void*)]);
            memcpy(newData, m_data, m_size * sizeof(void*));
            for (i32 index = m_size; index < newSize; ++index) {
                newData[index] = 0;
            }
            delete[] reinterpret_cast<BYTE*>(m_data); // byte-evidenced allocation owner
            m_data = newData;
            m_size = newSize;
            m_maxSize = newMaxSize;
        }
    }

    void** m_data;
    i32 m_size;
    i32 m_maxSize;
    i32 m_growBy;
};

inline i32 CTextPointerVector::Add(void* value) {
    i32 index = m_size;
    if (index >= m_size) {
        SetSize(index + 1);
    }
    m_data[index] = value;
    return index;
}

inline i32 CTextPointerVector::GetSize() const {
    return m_size;
}

// Retail owns one shared pointer vector for every loaded localization block.
// Each 16-byte descriptor records its allocation, entry count, and starting
// index in that vector. The original class name has not survived; this neutral
// name records only the executable-proven layout and operation.
class CTextBlock : public CObject {
public:
    CTextBlock();
    virtual ~CTextBlock();

    void Load(const char* resourcePath);
    char* operator[](i32 index);
    void Release();

    char* m_allocation;
    i32 m_count;
    i32 m_firstIndex;
};

extern CTextBlock g_itemNameText;
extern CTextPointerVector g_textLines;
extern CMapWordToPtr g_itemNames;

void LoadItemNames();

#endif // ROM1_TEXT_ITEMNAMES_H

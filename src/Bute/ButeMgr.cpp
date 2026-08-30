#include <rva.h>

#include <Bute/ButeMgr.h>

#include <Mfc.h>

#include <stdlib.h>
#include <string.h>

i32 DATA(0x001f20d8)
g_buteTraversalStopped = 0;

inline CRegException::CRegException(const char* value) {
    char* copy = new char[strlen(value) + 1];
    strcpy(copy, value);
    message = copy;
}

inline void CButeMgr::Record::SetName(const char* value) {
    if (value != name) {
        i32 length = strlen(value);
        if (length > 15) {
            flags |= BUTE_RECORD_NAME_TRUNCATED;
        }
        ++length;
        if (length > 15) {
            length = 15;
        }
        name[length] = 0;
        while (length--) {
            name[length] = value[length];
        }
    }
}

RVA(0x000cae40, 0x16c)
void CButeMgr::Read(CFile* file, u32 offset) {
    if (offset < BUTE_FILE_NO_OFFSET) {
        file->Seek(offset, CFile::begin);
    }

    file->Read(&m_root.signature, sizeof(m_root.signature));
    if (m_root.signature != BUTE_FILE_SIGNATURE) {
        const char* message = DATA_COMPGEN(0x001c1f64, "bad signature");
        throw CRegException(message);
    }
    file->Read(&m_root.value, sizeof(m_root.value));
    file->Read(&m_root.childCount, sizeof(m_root.childCount));
    file->Read(&m_root.flags, sizeof(m_root.flags));
    file->Read(&m_recordCount, sizeof(m_recordCount));
    file->Read(&m_textLength, sizeof(m_textLength));

    if (m_records != 0) {
        u32 count = m_recordCount;
        if (count == 0) {
            count = 1;
        }
        m_records = static_cast<Record*>(realloc(m_records, count * sizeof(Record)));
    } else {
        m_records = static_cast<Record*>(malloc(m_recordCount * sizeof(Record)));
    }
    if (m_records == 0) {
        AfxThrowMemoryException();
    }
    file->Read(m_records, m_recordCount * sizeof(Record));
    m_recordCapacity = m_recordCount;

    file->Read(&m_textSize, sizeof(m_textSize));
    m_textCapacity = m_textSize;

    TextPointer text;
    if (m_text != 0) {
        u32 size = m_textSize;
        if (size == 0) {
            size = 1;
        }
        text.opaque = realloc(m_text, size);
    } else {
        text.opaque = malloc(m_textSize);
    }
    m_text = text.text;
    if (m_text == 0) {
        AfxThrowMemoryException();
    }
    if (m_textSize != 0) {
        file->Read(m_text, m_textSize);
    }
}

// @dead-code: retained because FPO gives an exact standalone constructor.
// Zero-ref: no direct callers, relocated references, or live ILT forwarders in retail.
RVA(0x000cb050, 0x2e)
CButeMgr::CButeMgr(CFile* file, u32 offset) {
    ResetCurrentRecord();
    file->Read(m_root.name, sizeof(m_root.name));
    Read(file, offset);
}

RVA(0x000cb080, 0xb7)
CButeMgr::CButeMgr() {
    ResetCurrentRecord();

    m_textCapacity = BUTE_INITIAL_TEXT_CAPACITY;
    TextPointer text;
    text.opaque = malloc(BUTE_INITIAL_TEXT_CAPACITY);
    m_text = text.text;
    if (m_text == 0) {
        AfxThrowMemoryException();
    }
    m_textSize = 0;

    m_recordCapacity = BUTE_INITIAL_RECORD_CAPACITY;
    RecordPointer records;
    records.opaque = malloc(BUTE_INITIAL_RECORD_CAPACITY * sizeof(Record));
    m_records = records.record;
    if (m_records == 0) {
        AfxThrowMemoryException();
    }
    m_recordCount = 0;

    m_root.SetName(&afxChNil);
    m_root.signature = BUTE_FILE_SIGNATURE;
    m_root.value = 0;
    m_root.childCount = 0;
    m_root.flags = BUTE_RECORD_CONTAINER;
    m_textLength = 0;
}

// Located from the exact call/cleanup edges in GetMissionObjectCount. The MFC
// filename/open body remains the next Bute reconstruction slice; this claim
// provisions its real C++ identity for callers today.
RVA(0x000cb140, 0x1d2)
CButeMgr::CButeMgr(const char* filename) {
    (void)filename;
}

RVA(0x000cbf20, 0x25)
CButeMgr::~CButeMgr() {
    if (m_records != 0) {
        free(m_records);
    }
    if (m_text != 0) {
        free(m_text);
    }
}

RVA(0x000ccc00, 0x90)
i32 CButeMgr::GetInt(const char* tag, const char* key, i32 defaultValue) {
    Record* item = FindRecord(FindRecord(&m_root, tag), key);
    if (item != 0) {
        if ((item->flags & BUTE_RECORD_TYPE_MASK) != BUTE_RECORD_TYPE_INT) {
            const char* message =
                DATA_COMPGEN(0x001c2178, "not an int associated with specified key");
            throw CRegException(message);
        }
        return item->value;
    }
    return defaultValue;
}

RVA(0x000ce390, 0xa)
CButeMgr* CButeMgr::ResetCurrentRecord() {
    CButeMgr* result = this;
    result->m_currentRecord = 0;
    return result;
}

RVA(0x000ce7e0, 0x75)
CButeMgr::Record* CButeMgr::FindPath(char* path) {
    char value = *path;
    char* name = m_root.name;
    while (value != '\\' && value != '/' && value != 0 && *name != 0) {
        if (value != *name) {
            return 0;
        }
        ++name;
        ++path;
        value = *path;
    }
    if (*path != 0) {
        ++path;
    }

    Record* record = &m_root;
    while (*path != 0 && record != 0) {
        if ((record->flags & BUTE_RECORD_FINALIZE_MASK) != BUTE_RECORD_CONTAINER) {
            return 0;
        }
        record = FindPathComponent(record, &path);
    }
    return record;
}

RVA(0x000ce8a0, 0x1c)
void* CButeMgr::FindResourceRecord(char* path) {
    Record* record = FindPath(path);
    if (record != 0 && (record->flags & 0x40000010) != 0) {
        record = 0;
    }
    return record;
}

RVA(0x000ce8c0, 0xf6)
CButeMgr::Record* CButeMgr::FindRecord(Record* parent, const char* name) {
    if (parent == 0) {
        return 0;
    }

    Record* first = m_records + parent->value;
    if ((parent->flags & BUTE_RECORD_CHILDREN_SORTED) != 0 && parent->childCount > 0) {
        Record probe;
        probe.SetName(name);

        RecordPointer result;
        result.opaque =
            bsearch(&probe, first, parent->childCount, sizeof(Record), CompareRecordNames);
        return result.record;
    }

    u32 index;
    for (index = 0; index < parent->childCount;) {
        if (_strnicmp(name, first[index++].name, 15) == 0) {
            --index;
            break;
        }
    }
    if (index == parent->childCount) {
        return 0;
    }
    return first + index;
}

RVA(0x000ce9c0, 0x40)
CButeMgr::Record* CButeMgr::FindPathComponent(Record* parent, char** path) {
    char* end = *path;
    while (*end != '\\' && *end != '/' && *end != 0) {
        ++end;
    }

    char separator = *end;
    *end = 0;
    Record* result = FindRecord(parent, *path);
    *end = separator;
    if (separator != 0) {
        ++end;
    }
    *path = end;
    return result;
}

RVA(0x000cea00, 0x88)
void CButeMgr::FinalizeRecord(Record* record) {
    u32 state = record->flags & BUTE_RECORD_FINALIZE_MASK;
    if (state == 0) {
        record->flags |= BUTE_RECORD_FINALIZED;
        u32 type = (record->flags >> 1) & 7;
        if (type == BUTE_RECORD_KIND_INT || type == BUTE_RECORD_KIND_DOUBLE) {
            return;
        }
        m_textLength += record->childCount;
        return;
    }

    if (state == BUTE_RECORD_CONTAINER) {
        record->flags |= BUTE_RECORD_FINALIZED;
        for (u32 index = 0; index < record->childCount; ++index) {
            FinalizeRecord(m_records + record->value + index);
            if (g_buteTraversalStopped == 1) {
                break;
            }
        }
    }
}

RVA(0x000cea90, 0x33)
int __cdecl CButeMgr::CompareRecordIndices(const void* left, const void* right) {
    ConstRecordHandlePointer lhs;
    ConstRecordHandlePointer rhs;
    lhs.opaque = left;
    rhs.opaque = right;
    const Record* lhsRecord = *lhs.handle;
    const Record* rhsRecord = *rhs.handle;
    if (lhsRecord->value > rhsRecord->value) {
        return 1;
    }
    if (lhsRecord->value == rhsRecord->value) {
        return lhsRecord->childCount > rhsRecord->childCount;
    }
    return -1;
}

RVA(0x000cead0, 0x41)
int __cdecl CButeMgr::CompareRecordNames(const void* left, const void* right) {
    ConstRecordPointer lhs;
    ConstRecordPointer rhs;
    lhs.opaque = left;
    rhs.opaque = right;
    return strcmp(lhs.record->name, rhs.record->name);
}

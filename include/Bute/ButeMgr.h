#ifndef ROM1_BUTE_BUTEMGR_H
#define ROM1_BUTE_BUTEMGR_H

#include <Enums.h>
#include <Ints.h>

class CFile;

GZ_ENUM_CONST_BEGIN(ButeRecordFlags)
    BUTE_RECORD_CONTAINER = 1,
    BUTE_RECORD_TYPE_INT = 2,
    BUTE_RECORD_TYPE_MASK = 0xe,
    BUTE_RECORD_CHILDREN_SORTED = 0x10,
    BUTE_RECORD_NAME_TRUNCATED = 0x10000000,
    BUTE_RECORD_FINALIZE_MASK = 0x40000001,
    BUTE_RECORD_FINALIZED = 0x40000000,
GZ_ENUM_CONST_END(ButeRecordFlags)

GZ_ENUM_CONST_BEGIN(ButeRecordKind)
    BUTE_RECORD_KIND_INT = 1,
    BUTE_RECORD_KIND_DOUBLE = 2,
GZ_ENUM_CONST_END(ButeRecordKind)

GZ_ENUM_CONST_BEGIN(ButeFileConstants)
    BUTE_FILE_SIGNATURE = 0x31415926,
    BUTE_FILE_NO_OFFSET = -1,
    BUTE_INITIAL_RECORD_CAPACITY = 4,
    BUTE_INITIAL_TEXT_CAPACITY = 32,
GZ_ENUM_CONST_END(ButeFileConstants)

class CRegException {
public:
    char* message;

    CRegException(const char* value);
};

class CButeMgr {
public:
    CButeMgr(CFile* file, u32 offset);
    CButeMgr();
    CButeMgr(const char* filename);
    ~CButeMgr();

    i32 GetInt(const char* tag, const char* key, i32 defaultValue);

    // The retail resource archive reuses this record-tree layout and these
    // path walkers for its 32-byte index records.
    void* FindResourceRecord(char* path);

private:
    struct Record {
        u32 signature;
        u32 value;
        u32 childCount;
        u32 flags;
        char name[16];

        void SetName(const char* value);
    };

    union ConstRecordPointer {
        const void* opaque;
        const Record* record;
    };

    union RecordPointer {
        void* opaque;
        Record* record;
    };

    union TextPointer {
        void* opaque;
        char* text;
    };

    union ConstRecordHandlePointer {
        const void* opaque;
        Record* const* handle;
    };

    Record* FindRecord(Record* parent, const char* name);
    Record* FindPathComponent(Record* parent, char** path);
    Record* FindPath(char* path);
    void Read(CFile* file, u32 offset);
    void FinalizeRecord(Record* record);
    CButeMgr* ResetCurrentRecord();
    static int __cdecl CompareRecordNames(const void* left, const void* right);
    static int __cdecl CompareRecordIndices(const void* left, const void* right);

    Record m_root;
    u32 m_recordCount;
    u32 m_recordCapacity;
    Record* m_records;
    u32 m_currentRecord;
    u32 m_textLength;
    char* m_text;
    u32 m_textCapacity;
    u32 m_textSize;
};

#endif // ROM1_BUTE_BUTEMGR_H

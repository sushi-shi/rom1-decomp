#ifndef ROM1_BUTE_BUTEMGR_H
#define ROM1_BUTE_BUTEMGR_H

#include <Ints.h>

class CButeMgr {
public:
    CButeMgr(const char* filename);
    ~CButeMgr();

    i32 GetInt(const char* tag, const char* key, i32 defaultValue);

private:
    u8 m_storage[0x40];
};

#endif // ROM1_BUTE_BUTEMGR_H

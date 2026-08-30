#ifndef ROM1_NETWORK_LLDRIVER_H
#define ROM1_NETWORK_LLDRIVER_H

#include <MfcNoInline.h>

struct CConnectionInfo {
    char m_description[0x100];
    char m_address[0x100];
    DWORD m_kind;
    BYTE m_reserved204[0x10];
};

class CLlDriver {
public:
    CConnectionInfo* AppendConnectionInfo();
    void LoadIpConnectionInfo();

private:
    BYTE m_reserved000[0x14c];
    CConnectionInfo* m_connectionInfo;
    UINT m_connectionInfoCount;
};

#endif // ROM1_NETWORK_LLDRIVER_H

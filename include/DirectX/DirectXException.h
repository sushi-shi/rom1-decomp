#ifndef ROM1_DIRECTX_DIRECTXEXCEPTION_H
#define ROM1_DIRECTX_DIRECTXEXCEPTION_H

#include <MfcWin.h>

class CDirectXException {
public:
    CDirectXException(const char* message);

private:
    CString m_message;
    HRESULT m_result;
};

#endif // ROM1_DIRECTX_DIRECTXEXCEPTION_H

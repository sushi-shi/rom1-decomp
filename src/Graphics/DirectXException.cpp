#include <rva.h>

#include <DirectX/DirectXException.h>

RVA(0x00054860, 0x51)
CDirectXException::CDirectXException(const char* message) {
    m_message = message;
    m_result = 0;
}

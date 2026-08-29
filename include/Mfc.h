#ifndef ROM1_MFC_H
#define ROM1_MFC_H

// MFC platform root; do not mix it with the Win32.h prelude.

#define VC_EXTRALEAN

#include <afx.h>
#include <afxcoll.h>

// API-forced message-map member-pointer seam.
#define GZ_MFC_PMSG(method) reinterpret_cast<AFX_PMSG>(method)

extern "C" __declspec(dllimport) unsigned long WINAPI timeGetTime(void);

#endif // ROM1_MFC_H

#ifndef ROM1_MFCWIN_H
#define ROM1_MFCWIN_H

// Mfc.h must define _AFX_ENABLE_INLINES before this wrapper selects afxwin1.inl.
#include <Mfc.h>

#if defined(__clang__) || defined(ROM1_MFC_NO_INLINES)
#undef _AFX_ENABLE_INLINES
#endif
#include <afxwin.h>

#endif // ROM1_MFCWIN_H

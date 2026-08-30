#ifndef ROM1_SERIALIZATION_ARCHIVEOBJECTS_H
#define ROM1_SERIALIZATION_ARCHIVEOBJECTS_H

#include <MfcNoInline.h>

#include <afxtempl.h>

// The retail vtable at 0x19c630 inherits CObject's runtime-class entry but has
// its own Serialize slot.  No surviving class name is available, so this name
// records only the proven layout: a CObject-derived owner containing another
// polymorphic CObject at +0x04.
class CSerializableObjectHolder : public CObject {
public:
    virtual void Serialize(CArchive& archive);

private:
    CObject m_value;
};

// Runtime-class evidence preserves the name and 28-byte size of TableLine.
// Its first three fields are independently fixed by the serializer; the tail
// remains opaque until another method gives it semantic names.
class TableLine : public CObject {
public:
    static AFX_DATA CRuntimeClass classTableLine;
    virtual void Serialize(CArchive& archive);

    friend CArchive& AFXAPI operator>>(CArchive& archive, TableLine*& value);

    // Direct game-owned table consumers read the name field at +0x04.
    CString m_name;

protected:
    CArray<int, int> m_values;
};

// The anonymous retail subtypes below all return TableLine's runtime-class
// record. Their original C++ names therefore did not survive. The placeholder
// names state only the layouts and byte operations proven by their
// constructors and Serialize bodies.
class CTableLineWordBlock : public TableLine {
public:
    virtual void Serialize(CArchive& archive);

protected:
    WORD m_words[5];
    CStringArray m_strings;
};

class CTableLineRawBlock : public TableLine {
public:
    virtual void Serialize(CArchive& archive);

private:
    DWORD m_reserved2;
    BYTE m_bytes[0x48];
};

class CTableLineWordBlockLabel : public CTableLineWordBlock {
public:
    virtual void Serialize(CArchive& archive);

private:
    CString m_label;
};

class CTableLineStringPair : public TableLine {
public:
    virtual void Serialize(CArchive& archive);

private:
    CStringArray m_strings;
};

class CTableLineStringDecade : public TableLine {
public:
    virtual void Serialize(CArchive& archive);

private:
    CStringArray m_strings;
};

class CTableLineLabel : public TableLine {
public:
    virtual void Serialize(CArchive& archive);

private:
    CString m_label;
};

// One retail subtype overrides Serialize only to delegate to TableLine. Its
// original name did not survive, so retain an evidence-neutral placeholder.
class CTableLineBaseOnly : public TableLine {
public:
    virtual void Serialize(CArchive& archive);
};

#endif // ROM1_SERIALIZATION_ARCHIVEOBJECTS_H

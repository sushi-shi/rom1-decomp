#ifndef ROM1_SERIALIZATION_ARCHIVEOBJECTS_H
#define ROM1_SERIALIZATION_ARCHIVEOBJECTS_H

#include <MfcNoInline.h>

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
    virtual void Serialize(CArchive& archive);

private:
    CString m_name;
    CObject m_value;
    BYTE m_reserved[16];
};

// One retail subtype overrides Serialize only to delegate to TableLine. Its
// original name did not survive, so retain an evidence-neutral placeholder.
class CTableLineBaseOnly : public TableLine {
public:
    virtual void Serialize(CArchive& archive);
};

#endif // ROM1_SERIALIZATION_ARCHIVEOBJECTS_H

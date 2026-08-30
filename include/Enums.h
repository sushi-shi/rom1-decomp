#ifndef ROM1_ENUMS_H
#define ROM1_ENUMS_H

#include <Ints.h>

#if defined(__cplusplus) && __cplusplus >= 202002L
#define GZ_STRICT_ENUMS 1
#else
#define GZ_STRICT_ENUMS 0
#endif

#if GZ_STRICT_ENUMS

#define GZ_ENUM_BEGIN(name) enum class name : i32 {
#define GZ_ENUM_END(name)                                                                          \
    }                                                                                              \
    ;                                                                                              \
    using enum name;

#define GZ_ENUM_BEGIN_SPLIT(name, storage) enum class name : storage {
#define GZ_ENUM_END_SPLIT(name, storage)                                                           \
    }                                                                                              \
    ;                                                                                              \
    using enum name;

#define GZ_ENUM_FLAGS_BEGIN(name, storage) enum class name : storage {
#define GZ_ENUM_FLAGS_END(name, storage)                                                           \
    }                                                                                              \
    ;                                                                                              \
    using enum name;

#define GZ_ENUM_FORWARD(name) enum class name : i32
#define GZ_ENUM_FORWARD_SPLIT(name, storage) enum class name : storage

#define GZ_ENUM_STORAGE(name, storage) GzEnumStorage<name, storage>
#define GZ_ENUM_PARAM(name, storage) name
#define GZ_ENUM_RETURN(name, storage) name
#define GZ_ENUM_BITFIELD(name, storage) name

template<typename Enum, typename Storage> class GzEnumStorage {
public:
    GzEnumStorage() = default;
    constexpr GzEnumStorage(Enum value) : m_value(static_cast<Storage>(value)) {}
    constexpr GzEnumStorage(Storage value) : m_value(value) {}

    constexpr operator Enum() const {
        return static_cast<Enum>(m_value);
    }

    explicit constexpr operator i32() const {
        return static_cast<i32>(m_value);
    }

    GzEnumStorage& operator=(Enum value) {
        m_value = static_cast<Storage>(value);
        return *this;
    }

    GzEnumStorage& operator=(Storage value) {
        m_value = value;
        return *this;
    }

    GzEnumStorage& operator|=(Enum value) {
        m_value = static_cast<Storage>(m_value | static_cast<Storage>(value));
        return *this;
    }

    GzEnumStorage& operator&=(Enum value) {
        m_value = static_cast<Storage>(m_value & static_cast<Storage>(value));
        return *this;
    }

    GzEnumStorage& operator^=(Enum value) {
        m_value = static_cast<Storage>(m_value ^ static_cast<Storage>(value));
        return *this;
    }

private:
    Storage m_value;
};

template<typename Enum, typename Storage>
constexpr bool operator==(GzEnumStorage<Enum, Storage> lhs, Enum rhs) {
    return static_cast<Enum>(lhs) == rhs;
}

template<typename Enum, typename Storage>
constexpr bool operator!=(GzEnumStorage<Enum, Storage> lhs, Enum rhs) {
    return !(lhs == rhs);
}

template<typename Enum, typename LeftStorage, typename RightStorage>
constexpr bool
operator==(GzEnumStorage<Enum, LeftStorage> lhs, GzEnumStorage<Enum, RightStorage> rhs) {
    return static_cast<Enum>(lhs) == static_cast<Enum>(rhs);
}

template<typename Enum, typename LeftStorage, typename RightStorage>
constexpr bool
operator!=(GzEnumStorage<Enum, LeftStorage> lhs, GzEnumStorage<Enum, RightStorage> rhs) {
    return !(lhs == rhs);
}

template<typename Enum, typename Storage>
constexpr bool operator<(GzEnumStorage<Enum, Storage> lhs, Enum rhs) {
    return static_cast<Enum>(lhs) < rhs;
}

template<typename Enum, typename Storage>
constexpr bool operator>=(GzEnumStorage<Enum, Storage> lhs, Enum rhs) {
    return static_cast<Enum>(lhs) >= rhs;
}

template<typename Enum, typename Storage>
constexpr i32 GzEnumIndex(GzEnumStorage<Enum, Storage> value) {
    return static_cast<i32>(value);
}

template<typename Value> constexpr i32 GzEnumIndex(Value value) {
    return static_cast<i32>(value);
}

#define GZ_ENUM_FLAGS_OPS(name)                                                                    \
    inline constexpr name operator|(name a, name b) {                                              \
        return static_cast<name>(static_cast<i32>(a) | static_cast<i32>(b));                       \
    }                                                                                              \
    inline constexpr name operator&(name a, name b) {                                              \
        return static_cast<name>(static_cast<i32>(a) & static_cast<i32>(b));                       \
    }                                                                                              \
    inline constexpr name operator^(name a, name b) {                                              \
        return static_cast<name>(static_cast<i32>(a) ^ static_cast<i32>(b));                       \
    }                                                                                              \
    inline constexpr name operator~(name a) {                                                      \
        return static_cast<name>(~static_cast<i32>(a));                                            \
    }                                                                                              \
    inline constexpr name& operator|=(name& a, name b) {                                           \
        return a = a | b;                                                                          \
    }                                                                                              \
    inline constexpr name& operator&=(name& a, name b) {                                           \
        return a = a & b;                                                                          \
    }                                                                                              \
    inline constexpr name& operator^=(name& a, name b) {                                           \
        return a = a ^ b;                                                                          \
    }                                                                                              \
    inline constexpr bool operator!(name a) {                                                      \
        return !static_cast<i32>(a);                                                               \
    }

#define GZ_ENUM_STEPPED(name)                                                                      \
    inline constexpr name operator+(name a, i32 amount) {                                          \
        return static_cast<name>(static_cast<i32>(a) + amount);                                    \
    }                                                                                              \
    inline constexpr name operator-(name a, i32 amount) {                                          \
        return static_cast<name>(static_cast<i32>(a) - amount);                                    \
    }                                                                                              \
    inline constexpr i32 operator-(name a, name b) {                                               \
        return static_cast<i32>(a) - static_cast<i32>(b);                                          \
    }                                                                                              \
    inline name& operator+=(name& a, i32 amount) {                                                 \
        return a = a + amount;                                                                     \
    }                                                                                              \
    inline name& operator-=(name& a, i32 amount) {                                                 \
        return a = a - amount;                                                                     \
    }                                                                                              \
    inline name& operator++(name& a) {                                                             \
        return a = a + 1;                                                                          \
    }                                                                                              \
    inline name operator++(name& a, i32) {                                                         \
        name old = a;                                                                              \
        ++a;                                                                                       \
        return old;                                                                                \
    }                                                                                              \
    inline name& operator--(name& a) {                                                             \
        return a = a - 1;                                                                          \
    }                                                                                              \
    inline name operator--(name& a, i32) {                                                         \
        name old = a;                                                                              \
        --a;                                                                                       \
        return old;                                                                                \
    }

#else // !GZ_STRICT_ENUMS - the retail (MSVC 5.0) branch

#define GZ_ENUM_BEGIN(name) enum name {
#define GZ_ENUM_END(name)                                                                          \
    }                                                                                              \
    ;

#define GZ_ENUM_BEGIN_SPLIT(name, storage) enum name {
#define GZ_ENUM_END_SPLIT(name, storage)                                                           \
    }                                                                                              \
    ;

#define GZ_ENUM_FLAGS_BEGIN(name, storage) enum {
#define GZ_ENUM_FLAGS_END(name, storage)                                                           \
    }                                                                                              \
    ;                                                                                              \
    typedef i32 name;

#define GZ_ENUM_FORWARD(name) enum name
#define GZ_ENUM_FORWARD_SPLIT(name, storage) enum name

#define GZ_ENUM_STORAGE(name, storage) storage
#define GZ_ENUM_PARAM(name, storage) storage
#define GZ_ENUM_RETURN(name, storage) storage
#define GZ_ENUM_BITFIELD(name, storage) storage

#define GZ_ENUM_FLAGS_OPS(name)
#define GZ_ENUM_STEPPED(name)

#endif // GZ_STRICT_ENUMS

#define GZ_ENUM_CONST_BEGIN(name) enum {
#define GZ_ENUM_CONST_END(name)                                                                    \
    }                                                                                              \
    ;

#if GZ_STRICT_ENUMS
#define AT(a, i) (a)[GzEnumIndex(i)]
#define IDX(x) GzEnumIndex(x)
#define HAS(flags, bit) (IDX((flags) & (bit)))
#define BIT(x) (1 << IDX(x))
#else
#define AT(a, i) (a)[i]
#define IDX(x) (x)
#define HAS(flags, bit) ((flags) & (bit))
#define BIT(x) (1 << (x))
#endif

#endif // ROM1_ENUMS_H

#ifndef ROM1_CODEC_WORDRLE_H
#define ROM1_CODEC_WORDRLE_H

#include <Ints.h>

union ByteIntPointer {
    u8* bytes;
    i32* integer;
};

union ByteWordPointer {
    u8* bytes;
    u16* words;
};

struct WordRleEncodeState {
    ByteWordPointer outputCursor;
    i32 wordIndex;
    u16* inputCursor;
};

struct WordRleDecodeState {
    u16* outputCursor;
    i32 inputIndex;
    ByteWordPointer inputCursor;
};

struct WordRleEncodeTokenState {
    u8 count;
    u16* start;
    u16* cursor;
};

struct WordRleDecodeRepeatState {
    i32 count;
    u8* token;
    i32 index;
    ByteWordPointer data;
    u16 value;
};

// The retail stream is a sequence of 16-bit words.  Its first dword is the
// decoded word count; the remaining bytes are repeat and literal tokens.
void EncodeWordRle(u16* input, i32 wordCount, ByteIntPointer* output, i32* outputSize);
void DecodeWordRle(ByteIntPointer input, i32 inputSize, u16** output, i32* wordCount);

i32 EncodeWordRleRepeat(
    u16** input, i32 wordIndex, i32 wordCount, ByteWordPointer* output
    );
i32 EncodeWordRleLiteral(
    u16** input, i32 wordIndex, i32 wordCount, ByteWordPointer* output
    );
i32 DecodeWordRleRepeat(ByteWordPointer* input, u16** output);
i32 DecodeWordRleLiteral(ByteWordPointer* input, u16** output);

#endif // ROM1_CODEC_WORDRLE_H

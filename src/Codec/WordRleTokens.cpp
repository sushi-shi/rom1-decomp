#include <rva.h>

#include <Codec/WordRle.h>

#include <string.h>

RVA(0x00127040, 0xc4)
i32 EncodeWordRleRepeat(
    u16** input, i32 wordIndex, i32 wordCount, ByteWordPointer* output
    ) {
    WordRleEncodeTokenState state;

    state.cursor = *input + 1;
    state.start = *input;
    state.count = 1;

    while (state.cursor[-1] == state.cursor[0] && state.count < 0x7f
           && wordIndex + state.count < wordCount) {
        ++state.count;
        ++state.cursor;
    }

    *output->bytes = state.count | 0x80;
    ++output->bytes;
    *output->words = state.cursor[-1];
    ++output->words;
    *input += state.count;
    return state.count;
}

RVA(0x00127110, 0xff)
i32 EncodeWordRleLiteral(
    u16** input, i32 wordIndex, i32 wordCount, ByteWordPointer* output
    ) {
    WordRleEncodeTokenState state;

    state.cursor = *input + 1;
    state.start = *input;
    state.count = 1;

    while (state.cursor[-1] != state.cursor[0] && state.count < 0x7f
           && wordIndex + state.count < wordCount) {
        ++state.count;
        ++state.cursor;
    }
    if (wordIndex + state.count == wordCount) {
        ++state.count;
    }

    *output->bytes = state.count - 1;
    ++output->bytes;
    memcpy(output->bytes, *input, state.count * sizeof(u16) - sizeof(u16));
    output->bytes += state.count * sizeof(u16) - sizeof(u16);
    *input += state.count - 1;
    return state.count - 1;
}

RVA(0x00127210, 0x7b)
i32 DecodeWordRleRepeat(ByteWordPointer* input, u16** output) {
    WordRleDecodeRepeatState state;

    state.token = input->bytes;
    state.data.bytes = input->bytes + 1;
    state.count = *state.token & ~0x80;
    state.value = *state.data.words;

    for (state.index = 0; state.index < state.count; ++state.index) {
        **output = state.value;
        ++*output;
    }

    input->bytes += 3;
    return 3;
}

RVA(0x00127290, 0x67)
i32 DecodeWordRleLiteral(ByteWordPointer* input, u16** output) {
    u8* token = input->bytes;
    ByteWordPointer data;
    data.bytes = input->bytes + 1;
    i32 count = *token;

    memcpy(*output, data.bytes, count * sizeof(u16));
    *output += count;
    input->bytes += count * sizeof(u16) + 1;
    return count * sizeof(u16) + 1;
}

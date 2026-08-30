#include <rva.h>

#include <Codec/WordRle.h>

RVA(0x0011f130, 0xad)
void EncodeWordRle(
    u16* input, i32 wordCount, ByteIntPointer* output, i32* outputSize
    ) {
    WordRleEncodeState state;

    state.wordIndex = 0;
    state.inputCursor = input;

    output->bytes = new u8[wordCount * sizeof(u16)];
    state.outputCursor.bytes = output->bytes + sizeof(i32);
    *output->integer = wordCount;

    while (state.wordIndex < wordCount) {
        if (state.inputCursor[0] == state.inputCursor[1]) {
            state.wordIndex += EncodeWordRleRepeat(
                &state.inputCursor, state.wordIndex, wordCount, &state.outputCursor
                );
        } else {
            state.wordIndex += EncodeWordRleLiteral(
                &state.inputCursor, state.wordIndex, wordCount, &state.outputCursor
                );
        }
    }

    *outputSize = state.outputCursor.bytes - output->bytes;
}

RVA(0x0011f1e0, 0x94)
void DecodeWordRle(
    ByteIntPointer input, i32 inputSize, u16** output, i32* wordCount
    ) {
    WordRleDecodeState state;

    state.inputCursor.bytes = input.bytes + sizeof(i32);
    state.outputCursor = 0;

    *wordCount = *input.integer;
    *output = new u16[*wordCount];
    state.outputCursor = *output;

    state.inputIndex = sizeof(i32);
    while (state.inputIndex < inputSize) {
        if ((*state.inputCursor.bytes & 0x80) != 0) {
            state.inputIndex +=
                DecodeWordRleRepeat(&state.inputCursor, &state.outputCursor);
        } else {
            state.inputIndex +=
                DecodeWordRleLiteral(&state.inputCursor, &state.outputCursor);
        }
    }
}

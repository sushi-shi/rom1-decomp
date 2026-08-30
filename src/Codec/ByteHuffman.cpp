#include <rva.h>

#include <Codec/ByteHuffman.h>

#include <Mfc.h>

#include <stdlib.h>
#include <string.h>

RVA(0x000ef383, 0x1b)
ByteHuffmanPacker::ByteHuffmanPacker() {
    root = 0;
}

RVA(0x000ef39e, 0x13)
ByteHuffmanPacker::~ByteHuffmanPacker() {
    DestroyTree();
}

RVA(0x000ef3b1, 0x23)
void ByteHuffmanPacker::ClearStatistics() {
    memset(frequencies, 0, sizeof(frequencies));
}

RVA(0x000ef3d4, 0x5f)
void ByteHuffmanPacker::CountSymbols(u8* input, i32 inputSize) {
    ByteHuffmanCountState state;

    state.cursor = input;
    for (state.index = 0; state.index < inputSize; ++state.index, ++state.cursor) {
        ++frequencies[*state.cursor];
    }
}

RVA(0x000ef433, 0x26)
void ByteHuffmanPacker::SaveStatistics(CFile* file) {
    file->Write(frequencies, sizeof(frequencies));
}

RVA(0x000ef459, 0x48)
void ByteHuffmanPacker::LoadStatistics(CFile* file) {
    if (file->Read(frequencies, sizeof(frequencies)) != sizeof(frequencies)) {
        AfxThrowFileException(CFileException::endOfFile);
    }
    RebuildTree();
    BuildCodes();
}

RVA(0x000ef4a1, 0x2f)
i32 CompareByteHuffmanSymbolStats(const void* left, const void* right) {
    if (static_cast<const ByteHuffmanSymbolStats*>(left)->frequency
        < static_cast<const ByteHuffmanSymbolStats*>(right)->frequency) {
        return 1;
    }
    if (static_cast<const ByteHuffmanSymbolStats*>(left)->frequency
        > static_cast<const ByteHuffmanSymbolStats*>(right)->frequency) {
        return -1;
    }
    return 0;
}

RVA(0x000ef4d0, 0x1a3)
void ByteHuffmanPacker::RebuildTree() {
    ByteHuffmanSymbolStats stats[256];
    i32 index;

    for (index = 0; index < 256; ++index) {
        stats[index].symbol = static_cast<u8>(index);
        stats[index].frequency = frequencies[index];
    }
    qsort(stats, 256, sizeof(ByteHuffmanSymbolStats), CompareByteHuffmanSymbolStats);
    DestroyTree();

    root = new ByteHuffmanNode;
    root->weight = stats[0].frequency + 1;
    root->symbol = stats[0].symbol;
    for (index = 1; index < 256; ++index) {
        Insert(root, stats[index].symbol, stats[index].frequency + 1);
    }
}

RVA(0x000ef673, 0x167)
void ByteHuffmanPacker::Insert(ByteHuffmanNode* node, u8 symbol, i32 weight) {
    if (node->one == 0) {
        node->one = new ByteHuffmanNode;
        node->one->symbol = node->symbol;
        node->one->weight = node->weight;
        node->oneWeight = node->weight;

        node->zero = new ByteHuffmanNode;
        node->zero->symbol = symbol;
        node->zero->weight = weight;
        node->zeroWeight = weight;
    } else if (node->oneWeight <= node->zeroWeight) {
        Insert(node->one, symbol, weight);
        node->oneWeight += weight;
    } else {
        Insert(node->zero, symbol, weight);
        node->zeroWeight += weight;
    }
}

RVA(0x000ef7da, 0x4c)
void ByteHuffmanPacker::BuildCodes() {
    memset(codeBits, 0, sizeof(codeBits));
    memset(codes, 0, sizeof(codes));
    BuildCodes(root, 0, 0);
}

RVA(0x000ef826, 0x8c)
void ByteHuffmanPacker::BuildCodes(ByteHuffmanNode* node, u32 code, i32 bitCount) {
    if (node->one == 0 && node->zero == 0) {
        codes[node->symbol] = code >> (32 - bitCount);
        codeBits[node->symbol] = bitCount;
    } else {
        BuildCodes(node->one, (code >> 1) | 0x80000000, bitCount + 1);
        BuildCodes(node->zero, code >> 1, bitCount + 1);
    }
}

RVA(0x000ef8b2, 0x2a)
void ByteHuffmanPacker::DestroyTree() {
    DestroyNode(root);
    root = 0;
}

RVA(0x000ef8dc, 0x44)
void ByteHuffmanPacker::DestroyNode(ByteHuffmanNode* node) {
    if (node != 0) {
        DestroyNode(node->one);
        DestroyNode(node->zero);
        delete node;
    }
}

RVA(0x000ef920, 0x19)
i32 ByteCountForBits(i32 bitCount) {
    return (bitCount >> 3) + ((bitCount & 7) != 0);
}

RVA(0x000ef939, 0xcb)
i32 ByteHuffmanPacker::Pack(u8* input, i32 inputSize, u32* output) {
    i32 outputBit;
    i32 totalBits;
    u32* outputCursor;
    u8* inputCursor;

    inputCursor = input;
    outputCursor = output;
    totalBits = 0;
    outputBit = 0;
    *outputCursor = 0;
    for (; inputSize != 0; ++inputCursor, --inputSize) {
        i32 bitCount;
        u32 code;

        code = codes[*inputCursor];
        bitCount = codeBits[*inputCursor];
        totalBits += bitCount;
        *outputCursor |= code << outputBit;
        outputBit += bitCount;
        if (outputBit >= 32) {
            outputBit -= 32;
            ++outputCursor;
            *outputCursor = code >> (32 - outputBit + bitCount);
        }
    }
    return totalBits;
}

RVA(0x000efa04, 0xd6)
i32 ByteHuffmanPacker::Unpack(u32* input, i32 inputBits, u8* output, i32 outputSize) {
    ByteHuffmanUnpackState state;

    state.inputCursor = input;
    state.outputCursor = output;
    state.outputCount = 0;
    state.inputWordBits = 0;
    for (; inputBits > 0; ++state.outputCount) {
        state.node = root;
        for (; state.node->one != 0; --state.inputWordBits, --inputBits) {
            if (state.inputWordBits == 0) {
                state.inputWordBits = 32;
                state.inputWord = *state.inputCursor;
                ++state.inputCursor;
            }
            if ((state.inputWord & 1) != 0) {
                state.node = state.node->one;
            } else {
                state.node = state.node->zero;
            }
            state.inputWord >>= 1;
        }
        if (outputSize != 0) {
            *state.outputCursor = state.node->symbol;
            --outputSize;
            ++state.outputCursor;
        }
    }
    return state.outputCount;
}

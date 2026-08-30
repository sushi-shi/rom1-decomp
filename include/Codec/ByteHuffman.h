#ifndef ROM1_CODEC_BYTEHUFFMAN_H
#define ROM1_CODEC_BYTEHUFFMAN_H

#include <Ints.h>

class CFile;

struct ByteHuffmanNode {
    ByteHuffmanNode();

    ByteHuffmanNode* one;
    ByteHuffmanNode* zero;
    i32 oneWeight;
    i32 zeroWeight;
    u8 symbol;
    u8 padding[3];
    i32 weight;
};

struct ByteHuffmanSymbolStats {
    u8 symbol;
    u8 padding[3];
    i32 frequency;
};

struct ByteHuffmanCountState {
    u8* cursor;
    i32 index;
};

struct ByteHuffmanUnpackState {
    ByteHuffmanNode* node;
    u8* outputCursor;
    i32 inputWordBits;
    u32 inputWord;
    i32 outputCount;
    u32* inputCursor;
};

class ByteHuffmanPacker {
public:
    ByteHuffmanPacker();
    ~ByteHuffmanPacker();

    void ClearStatistics();
    void CountSymbols(u8* input, i32 inputSize);
    void SaveStatistics(CFile* file);
    void LoadStatistics(CFile* file);
    void RebuildTree();
    void Insert(ByteHuffmanNode* node, u8 symbol, i32 weight);
    void BuildCodes();
    void BuildCodes(ByteHuffmanNode* node, u32 code, i32 bitCount);
    void DestroyTree();
    void DestroyNode(ByteHuffmanNode* node);
    i32 Pack(u8* input, i32 inputSize, u32* output);
    i32 Unpack(u32* input, i32 inputBits, u8* output, i32 outputSize);

    u32 codes[256];
    i32 codeBits[256];
    i32 frequencies[256];
    ByteHuffmanNode* root;
};

i32 CompareByteHuffmanSymbolStats(const void* left, const void* right);
i32 ByteCountForBits(i32 bitCount);

#endif // ROM1_CODEC_BYTEHUFFMAN_H

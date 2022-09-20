'''
网易云音乐ncm格式解密

作者：HuangFuSL

依赖包：pycryptodomex

参数格式：
输入一个ncm文件路径或包含ncm的目录路径，省略则处理当前目录下的所有ncm文件

输出格式
解码后的音频文件，mp3或flac格式
'''
from __future__ import annotations

import base64
import functools
import io
import json
import os
import sys
from typing import Tuple

from Cryptodome.Cipher import AES

NCM_FILEHEAD = b'CTENFDAM'
NCM_COREKEY = b'hzHRAmso5kInbaxW'
NCM_SIDEKEY = b"#14ljk_!\\]&0U<'("


def unpad(s: str | bytes):
    ''' 清除数据后面填充的字节块 '''
    return s[0: -s[-1]] if isinstance(s, bytes) else unpad(s.encode('utf-8'))


def aes_decrypt(key: bytes, data: bytes) -> bytes:
    ''' AES解密 '''
    return AES.new(key, AES.MODE_ECB).decrypt(data)


def xor(data: bytes, num: int | bytes):
    ''' 利用整数运算进行bytes对象的快速异或 '''
    if isinstance(num, int):
        num = bytes([num] * len(data))
    b2i = functools.partial(int.from_bytes, byteorder='little')
    return (b2i(data) ^ b2i(num)).to_bytes(len(data), 'little')


def add(a: int, b: int):
    ''' 包含整型溢出的相加 '''
    return (a + b) & 0xff


def build_keybox(decrypted: bytes):
    ''' 构造解密文件的函数 '''
    bytemap = bytearray(range(256))
    b, i = 0, 0
    for _ in range(256):
        b = add(bytemap[_], b + decrypted[i])
        i = (i + 1) % len(decrypted)
        bytemap[_], bytemap[b] = bytemap[b], bytemap[_]
    keybox = bytes(
        bytemap[add(bytemap[add(_, i)], _)]
        for i, _ in enumerate(bytemap[1:] + bytemap[:1], 1)
    )

    def apply_keybox(data: bytes):
        return xor(data, (keybox * (len(data) // 256 + 1))[:len(data)])
    return apply_keybox


def read_chunk(data: io.BytesIO) -> bytes:
    ''' 分块读取文件，前4字节表示块长度 '''
    chunk_size = int.from_bytes(data.read(4), 'little')
    return data.read(chunk_size)


def ncm_decrypt(data: io.BytesIO) -> Tuple[str, bytes]:
    ''' 解密ncm文件 '''
    core_key_chunk = read_chunk(data)
    decrypted = unpad(aes_decrypt(NCM_COREKEY, xor(core_key_chunk, 100)))[17:]
    keybox = build_keybox(decrypted) # 用于文件主体的解密

    b64_chunk = xor(read_chunk(data), 99) # 元数据部分
    b64_chunk_data = base64.b64decode(b64_chunk.split(b':', 1)[1])
    mdc = json.loads(unpad(aes_decrypt(NCM_SIDEKEY, b64_chunk_data)[6:]))
    file_name = '{musicName} - {artist[0][0]}.{format}'.format(**mdc)

    data.seek(9, 1)
    image = read_chunk(data) # 专辑封面
    w = io.BytesIO()
    while True:
        chunk = data.read(32768)
        if not chunk:
            break
        w.write(keybox(chunk))

    return file_name, w.getvalue()


def process_file(path: str, output_dir: str):
    with open(path, 'rb') as f:
        if f.read(8) != NCM_FILEHEAD:
            raise Exception('Not a NCM file')
        f.seek(2, 1)
        fn, data = ncm_decrypt(io.BytesIO(f.read()))
    with open(os.path.join(output_dir, fn), 'wb') as f:
        f.write(data)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else '.'
    if os.path.isdir(path):
        for _ in os.listdir(path):
            if _.endswith('.ncm'):
                process_file(os.path.join(path, _), path)
    elif path.endswith('.ncm'):
        process_file(path, os.path.dirname(path))

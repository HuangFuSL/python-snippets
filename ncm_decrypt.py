'''
网易云音乐ncm格式解密

作者：HuangFuSL

依赖包：pycryptodomex

参数格式：
path [path ...] [-o OUTPUT] [-f] [-r REGEX] [-e EXCLUDE] [-q] [-v]

- path：ncm文件或目录
- -o, --output：输出目录
- -f, --force：覆盖已存在的文件
- -r, --regex：匹配文件名的正则表达式
- -e, --exclude：排除文件名的正则表达式
- -q, --quiet：不打印处理信息
- -v, --verbose：打印调试信息

输出格式
解码后的音频文件，mp3或flac格式
'''
from __future__ import annotations

import argparse
import base64
import functools
import io
import json
import logging
import math
import os
import re
from typing import Tuple

from Cryptodome.Cipher import AES

NCM_FILEHEAD = b'CTENFDAM'
NCM_COREKEY = b'hzHRAmso5kInbaxW'
NCM_SIDEKEY = b"#14ljk_!\\]&0U<'("
ARG_HELP = {
    ('path', ): 'NCM file or directory',
    ('-o', '--output'): 'Output directory',
    ('-f', '--force'): 'Overwrite existing files',
    ('-r', '--regex'): 'Regex to match filename',
    ('-e', '--exclude'): 'Regex to exclude filename',
    ('-q', '--quiet'): 'Do not print processing info',
    ('-v', '--verbose'): 'Print debug info'
}
ARG_TEMPLATE = {
    ('path', ): {'nargs': '*', 'default': '.'},
    ('-o', '--output'): {'type': str, 'default': None},
    ('-f', '--force'): {'action': 'store_true'},
    ('-r', '--regex'): {'type': str, 'default': None},
    ('-e', '--exclude'): {'type': str, 'default': None},
    ('-q', '--quiet'): {'action': 'store_true'},
    ('-v', '--verbose'): {'action': 'store_true'}
}
UNITS = ['B', 'KB', 'MB', 'GB', 'TB']


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
    keybox = build_keybox(decrypted)  # 用于文件主体的解密

    b64_chunk = xor(read_chunk(data), 99)  # 元数据部分
    b64_chunk_data = base64.b64decode(b64_chunk.split(b':', 1)[1])
    mdc = json.loads(unpad(aes_decrypt(NCM_SIDEKEY, b64_chunk_data)[6:]))
    file_name = '{musicName} - {artist[0][0]}.{format}'.format(**mdc)

    data.seek(9, 1)
    _ = read_chunk(data)  # 专辑封面
    w = io.BytesIO()
    while True:
        chunk = data.read(32768)
        if not chunk:
            break
        w.write(keybox(chunk))

    return file_name, w.getvalue()


def process_file(src: str, output_dir: str, force: bool = False) -> int:
    with open(src, 'rb') as f:
        if f.read(8) != NCM_FILEHEAD:
            raise Exception('Not a NCM file')
        f.seek(2, 1)
        fn, data = ncm_decrypt(io.BytesIO(f.read()))
    dest = os.path.join(output_dir, fn.translate(
        str.maketrans(r'\/:*?"<>|', '_' * 9)))
    if force or not os.path.exists(dest):
        logging.debug('    Processing %s', dest)
        with open(dest, 'wb') as f:
            f.write(data)
        return len(data)

    logging.debug('    Skipping %s', dest)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NCM converter')
    for args, msg in ARG_HELP.items():
        parser.add_argument(*args, **ARG_TEMPLATE[args], help=msg)
    ns = parser.parse_args()

    levels = [logging.INFO, logging.ERROR, logging.DEBUG, logging.DEBUG]
    logging.basicConfig(
        level=levels[ns.quiet + ns.verbose * 2],
        format='%(message)s',
    )

    logging.info('Path:')
    for path in ns.path:
        abspath = os.path.abspath(path)
        if abspath.startswith(path) or path.startswith(abspath):
            logging.info('    %s', path)
        else:
            logging.info('    %s (%s)', path, abspath)
    logging.info('Output: %s', ns.output or 'Same as input')
    logging.info('Force: %s', ns.force)
    logging.info('Regex: %s', ns.regex or 'None')
    logging.info('Exclude: %s', ns.exclude or 'None')
    logging.info('Logging level: %s', logging.getLevelName(
        logging.getLogger().level))

    processed, skipped, size = 0, 0, 0

    for path in ns.path:
        for root, _, files in os.walk(path):
            targets = [
                _ for _ in files
                if all([
                    _.endswith('.ncm'),
                    not ns.regex or re.search(ns.regex, _),
                    not ns.exclude or not re.search(ns.exclude, _)
                ])
            ]
            if targets:
                logging.debug('Entering %s', root)
                for file in targets:
                    try:
                        output_size = process_file(
                            os.path.join(root, file), ns.output or root, ns.force
                        )
                        size += output_size
                        if output_size:
                            processed += 1
                        else:
                            skipped += 1
                    except Exception as e:
                        logging.error('Error processing %s: %s', file, e)
                logging.debug('Leaving %s', root)
    if size:
        size_unit = min(int(math.log2(size) / 10), len(UNITS) - 1)
        size_str = f'{size / 1024 ** size_unit:.2f}{UNITS[size_unit]}'
    else:
        size_str = '0B'
        logging.warning('No files processed')
    logging.info(
        'Processed %d files, skipped %d files, total size %s',
        processed, skipped, size_str
    )

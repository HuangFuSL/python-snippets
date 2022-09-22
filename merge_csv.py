'''
CSV文件合并

作者：HuangFuSL
'''

import argparse
import os
import itertools
import csv
from typing import Iterator, List, Tuple, TypeVar

T = TypeVar('T')

def extract_head(s: Iterator[T]) -> Tuple[T, List[T]]:
    return next(s), list(s)

def load_csv(file: str):
    with open(file, 'r', encoding='utf-8', newline='') as f:
        dialect = csv.Sniffer().sniff(f.read(), delimiters=',')
        f.seek(0)
        return extract_head(csv.reader(f, dialect=dialect))
    

def merge_csv(dest: str, *src: str, encoding: str):
    dest_head = tuple()
    wf = open(dest, 'w', encoding=encoding, newline='')
    writer = csv.writer(wf)
    for file in src:
        head, content = load_csv(file)
        if not dest_head:
            dest_head = tuple(head)
            writer.writerow(dest_head)
            
        writer.writerows(content)
    wf.close()

def search(path: str, recursive: bool):
    if not recursive:
        yield from [
            os.path.join(path, f)
            for f in os.listdir(path)
                if f.endswith('.csv')
        ]
    for root, _, files in os.walk(path):
        yield from [
            os.path.join(path, root, f)
            for f in files
                if f.endswith('.csv')
        ]

parser = argparse.ArgumentParser(description='Merge CSV Sheets')
parser.add_argument(
    '-o', '--output', nargs=1, default='output.csv',
    help='Path to output file'
    )
parser.add_argument(
    '-R', '--recursive', action='store_true',
    help='Search files recursively when directory is specified'
)
parser.add_argument(
    '-e', '--encoding', default='utf-8',
    help='Output encoding'
)
parser.add_argument('files', nargs='*', help='Files to merge')

if __name__ == '__main__':
    ns = parser.parse_args()
    files = [_ for _ in ns.files if os.path.isfile(_)]
    dirs = [_ for _ in ns.files if os.path.isdir(_)]
    targets = itertools.chain(files, *map(lambda d: search(d, ns.recursive), dirs))
    merge_csv(ns.output, *targets, encoding=ns.encoding)

"""JSON 말뭉치 1개의 구조를 파악한다."""
import json
from pathlib import Path

RAW = Path("data/raw")
files = sorted(RAW.rglob("*.json"))
print(f"JSON 파일 {len(files)}개\n")

# 접두사별 개수
from collections import Counter
pre = Counter(f.name[:4] for f in files)
print("파일명 접두사별 개수:")
for k, v in pre.items():
    print(f"  {k}: {v}개")
print()

f = files[0]
print(f"샘플 파일: {f.name}  ({f.stat().st_size/1024**2:.0f} MB)")
print("=" * 72)

with open(f, encoding="utf-8") as fp:
    data = json.load(fp)

def peek(obj, depth=0):
    pad = "  " * depth
    if depth > 4:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict):
                print(f"{pad}{k}: dict")
                peek(v, depth + 1)
            elif isinstance(v, list):
                print(f"{pad}{k}: list (len={len(v)})")
                if v:
                    peek(v[0], depth + 1)
            else:
                print(f"{pad}{k}: {type(v).__name__} = {str(v)[:60]!r}")
    elif isinstance(obj, list) and obj:
        peek(obj[0], depth + 1)

peek(data)``
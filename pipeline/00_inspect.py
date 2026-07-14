"""data/raw/ 의 모든 CSV를 훑어 연도별 현황을 요약한다."""
import pandas as pd
from pathlib import Path
from collections import Counter, defaultdict

RAW = Path("data/raw")
files = sorted(RAW.rglob("*.csv"))
print(f"CSV 파일 {len(files)}개 발견\n")

year_sent = Counter()
year_files = defaultdict(set)
total_gb = 0

for f in files:
    gb = f.stat().st_size / 1024**3
    total_gb += gb
    c = Counter()
    try:
        for chunk in pd.read_csv(f, usecols=['date'], dtype={'date': str},
                                 chunksize=200_000, on_bad_lines='skip'):
            c.update(chunk['date'].astype(str).str[:4])
    except Exception as e:
        print(f"  [실패] {f.name}: {e}")
        continue

    years = sorted(c)
    label = f"{years[0]}~{years[-1]}" if len(years) > 1 else (years[0] if years else "?")
    print(f"  {f.relative_to(RAW).as_posix():48s} {gb:6.2f}GB  기사연도: {label}")

    for y, n in c.items():
        year_sent[y] += n
        year_files[y].add(f.name)

print("\n" + "=" * 72)
print(f"CSV 총 용량: {total_gb:.2f} GB\n")
print("연도별 문장 수:")
for y in sorted(year_sent):
    print(f"  {y}: {year_sent[y]:>13,} 문장   ({len(year_files[y])}개 파일)")

if year_sent:
    lo, hi = int(min(year_sent)), int(max(year_sent))
    missing = [str(y) for y in range(lo, hi + 1) if str(y) not in year_sent]
    print(f"\n연도 범위: {lo} ~ {hi}")
    print(f"빠진 연도: {missing if missing else '없음'}")
"""
01_extract.py
=============
국립국어원 신문 말뭉치(CSV + JSON)에서 (year, sentence)만 뽑아 연도별 parquet로 저장한다.

정찰 결과 요약 (회의록 참고):
  - 분석 범위: 2009 ~ 2024 (2004~2008은 노이즈 수준이라 제외)
  - 파일명/최상위 metadata.year는 '구축 연도'일 뿐이다. 반드시 문서 내부의 date 필드만 신뢰할 것.
  - CSV: 한 행 = 한 문장. 필요한 컬럼은 date, sentence 뿐.
  - JSON: document[i].metadata.date / document[i].paragraph[j].form
          form에는 <p> 태그가 붙어 있으므로 반드시 제거.

28.5GB를 한 번에 메모리에 올리지 않도록 CSV는 청크 단위로, JSON은 파일 단위로 처리하고
연도별로 나눠서 즉시 디스크에 흘려보낸다(append). 오래 걸리므로 백그라운드 실행을 권장한다.

실행:
    python pipeline/01_extract.py --corpus-dir /path/to/corpus --out-dir data/extracted
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

import pandas as pd

FIRST_YEAR = 2009
LAST_YEAR = 2024
CSV_CHUNKSIZE = 200_000
P_TAG_RE = re.compile(r"</?p\s*/?>", flags=re.IGNORECASE)


def _year_from_date(raw) -> int | None:
    """date 필드('20230101' 형태 또는 유사)에서 연도를 안전하게 뽑아낸다."""
    if raw is None:
        return None
    s = str(raw).strip()
    if len(s) < 4 or not s[:4].isdigit():
        return None
    year = int(s[:4])
    if FIRST_YEAR <= year <= LAST_YEAR:
        return year
    return None


def _writer_for(out_dir: pathlib.Path, year: int):
    """연도별 parquet writer. pyarrow가 없으면 csv로 append."""
    path_parquet = out_dir / f"{year}.parquet"
    path_csv = out_dir / f"{year}.csv"
    return path_parquet, path_csv


def _flush(rows: dict[int, list[str]], out_dir: pathlib.Path) -> None:
    for year, sentences in rows.items():
        if not sentences:
            continue
        df = pd.DataFrame({"year": year, "sentence": sentences})
        path_parquet, path_csv = _writer_for(out_dir, year)
        try:
            if path_parquet.exists():
                existing = pd.read_parquet(path_parquet)
                df = pd.concat([existing, df], ignore_index=True)
            df.to_parquet(path_parquet, index=False)
        except (ImportError, ValueError):
            # pyarrow 미설치 환경 대비 fallback
            header = not path_csv.exists()
            df.to_csv(path_csv, index=False, mode="a", header=header)
        sentences.clear()


def extract_csv(path: pathlib.Path, out_dir: pathlib.Path, buffer: dict[int, list[str]], flush_every: int) -> int:
    n = 0
    for chunk in pd.read_csv(path, usecols=["date", "sentence"], chunksize=CSV_CHUNKSIZE, dtype=str):
        for date, sentence in zip(chunk["date"], chunk["sentence"]):
            year = _year_from_date(date)
            if year is None or not isinstance(sentence, str) or not sentence.strip():
                continue
            buffer.setdefault(year, []).append(sentence.strip())
            n += 1
        if n >= flush_every:
            _flush(buffer, out_dir)
            n = 0
    _flush(buffer, out_dir)
    return n


def extract_json(path: pathlib.Path, out_dir: pathlib.Path, buffer: dict[int, list[str]], flush_every: int) -> int:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    documents = data.get("document", [])
    n = 0
    for doc in documents:
        year = _year_from_date(doc.get("metadata", {}).get("date"))
        if year is None:
            continue
        for para in doc.get("paragraph", []):
            form = para.get("form")
            if not form:
                continue
            clean = P_TAG_RE.sub("", form).strip()
            if not clean:
                continue
            buffer.setdefault(year, []).append(clean)
            n += 1
        if n >= flush_every:
            _flush(buffer, out_dir)
            n = 0
    _flush(buffer, out_dir)
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-dir", required=True, type=pathlib.Path, help="말뭉치 원본이 있는 폴더 (CSV/JSON 혼재)")
    ap.add_argument("--out-dir", default=pathlib.Path("data/extracted"), type=pathlib.Path)
    ap.add_argument("--flush-every", type=int, default=500_000, help="이 개수마다 디스크로 flush")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(args.corpus_dir.rglob("*.csv"))
    json_files = sorted(args.corpus_dir.rglob("*.json"))
    print(f"CSV {len(csv_files)}개, JSON {len(json_files)}개 발견. 대상: {FIRST_YEAR}~{LAST_YEAR}")

    buffer: dict[int, list[str]] = {}
    total = 0
    t0 = time.time()

    for i, path in enumerate(csv_files, 1):
        try:
            total += extract_csv(path, args.out_dir, buffer, args.flush_every)
        except Exception as e:  # noqa: BLE001 - 개별 파일 오류로 전체가 멈추지 않게
            print(f"  [warn] {path.name} 처리 실패: {e}", file=sys.stderr)
        print(f"  [csv {i}/{len(csv_files)}] {path.name} 누적 {total:,}문장  ({time.time()-t0:.0f}s)")

    for i, path in enumerate(json_files, 1):
        try:
            total += extract_json(path, args.out_dir, buffer, args.flush_every)
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] {path.name} 처리 실패: {e}", file=sys.stderr)
        print(f"  [json {i}/{len(json_files)}] {path.name} 누적 {total:,}문장  ({time.time()-t0:.0f}s)")

    print(f"완료: 총 {total:,}문장 -> {args.out_dir}")


if __name__ == "__main__":
    main()

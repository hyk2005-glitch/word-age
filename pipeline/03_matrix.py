"""
03_matrix.py
=============
02_tokenize.py가 만든 연도별 단어 카운트를 하나의 연도x단어 행렬(long format)로 합치고,
per-million 정규화를 적용한다.

    per_million = count / 해당연도_총어절수 * 1,000,000

연도마다 말뭉치(및 샘플) 크기가 다르므로 원시 카운트를 그대로 쓰면 안 된다.
그렇게 하면 문서 수가 많다는 이유만으로 모든 단어가 최근에 정점을 찍은 것처럼
보이고, '언어 나이'가 전부 최근으로 쏠려 서비스 자체가 무의미해진다.

실행:
    python pipeline/03_matrix.py --in-dir data/tokenized --out data/matrix/word_year_permillion.parquet
"""

from __future__ import annotations

import argparse
import pathlib

import pandas as pd


def _read(path_parquet: pathlib.Path, path_csv: pathlib.Path) -> pd.DataFrame:
    if path_parquet.exists():
        try:
            return pd.read_parquet(path_parquet)
        except (ImportError, ValueError):
            pass
    if path_csv.exists():
        return pd.read_csv(path_csv)
    raise FileNotFoundError(f"{path_parquet} 또는 {path_csv}를 찾을 수 없다.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in-dir", default=pathlib.Path("data/tokenized"), type=pathlib.Path)
    ap.add_argument("--out", default=pathlib.Path("data/matrix/word_year_permillion.parquet"), type=pathlib.Path)
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    totals = _read(args.in_dir / "year_totals.parquet", args.in_dir / "year_totals.csv")
    totals = totals.set_index("year")["total_tokens"]

    count_files = sorted(args.in_dir.glob("*_counts.parquet")) or sorted(args.in_dir.glob("*_counts.csv"))
    if not count_files:
        raise SystemExit(f"{args.in_dir}에 *_counts 파일이 없다. 먼저 02_tokenize.py를 실행할 것.")

    frames = []
    for path in count_files:
        year = int(path.name.split("_counts")[0])
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        df["year"] = year
        frames.append(df)

    matrix = pd.concat(frames, ignore_index=True)
    matrix["total_tokens"] = matrix["year"].map(totals)
    matrix["per_million"] = matrix["count"] / matrix["total_tokens"] * 1_000_000

    matrix = matrix[["year", "word", "count", "per_million"]].sort_values(["word", "year"])

    try:
        matrix.to_parquet(args.out, index=False)
    except (ImportError, ValueError):
        csv_out = args.out.with_suffix(".csv")
        matrix.to_csv(csv_out, index=False)
        print(f"[skip] parquet 저장 실패 -> {csv_out}로 대체 저장")
        return

    print(f"완료: {matrix['word'].nunique():,}개 단어 x {matrix['year'].nunique()}개 연도 -> {args.out}")


if __name__ == "__main__":
    main()

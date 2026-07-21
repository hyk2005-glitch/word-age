"""
02_tokenize.py
===============
01_extract.py가 만든 연도별 문장에서 Kiwi로 명사를 추출하고, 연도별 단어 빈도와
'해당연도 총 어절수'를 함께 기록한다. 총 어절수는 03_matrix.py의 per-million
정규화 분모로 쓰이므로 반드시 같이 저장한다.

MAX_PER_YEAR:
  28.5GB 전체를 Kiwi로 돌리면 하루 이상 걸린다. 먼저 300_000으로 파이프라인을
  검증하고, 결과가 말이 되면 1_000_000으로 재실행한다. 연도마다 동일한 수를
  샘플링하므로 상대빈도는 거의 그대로 유지된다.

실행:
    python pipeline/02_tokenize.py --in-dir data/extracted --out-dir data/tokenized \
        --max-per-year 300000
"""

from __future__ import annotations

import argparse
import pathlib
import time

import pandas as pd

DEFAULT_MAX_PER_YEAR = 300_000  # 검증용. 최종은 1_000_000.
NOUN_TAGS = {"NNG", "NNP"}  # 일반명사 / 고유명사


def load_stopwords(path: pathlib.Path) -> set[str]:
    if not path.exists():
        return set()
    words = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.add(line)
    return words


def _read_year_sentences(in_dir: pathlib.Path, year: int) -> pd.DataFrame | None:
    parquet_path = in_dir / f"{year}.parquet"
    csv_path = in_dir / f"{year}.csv"
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except (ImportError, ValueError):
            pass
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return None


def _get_kiwi():
    try:
        from kiwipiepy import Kiwi
    except ImportError as e:
        raise SystemExit(
            "kiwipiepy가 설치되어 있지 않다. `pip install kiwipiepy` 후 다시 실행할 것."
        ) from e
    return Kiwi()


def tokenize_year(
    kiwi, sentences: pd.Series, stopwords: set[str]
) -> tuple[pd.Series, int]:
    """returns (명사 빈도 Series, 총 어절수)"""
    counts: dict[str, int] = {}
    total_tokens = 0

    for result in kiwi.analyze(list(sentences), top_n=1):
        tokens = result[0][0]  # (형태소 리스트, 점수) 중 최상위 1개
        total_tokens += len(tokens)
        for token in tokens:
            if token.tag in NOUN_TAGS and len(token.form) >= 2 and token.form not in stopwords:
                counts[token.form] = counts.get(token.form, 0) + 1

    return pd.Series(counts, name="count"), total_tokens


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in-dir", default=pathlib.Path("data/extracted"), type=pathlib.Path)
    ap.add_argument("--out-dir", default=pathlib.Path("data/tokenized"), type=pathlib.Path)
    ap.add_argument("--stopwords", default=pathlib.Path("config/stopwords.txt"), type=pathlib.Path)
    ap.add_argument("--max-per-year", type=int, default=DEFAULT_MAX_PER_YEAR)
    ap.add_argument("--seed", type=int, default=20260721)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stopwords = load_stopwords(args.stopwords)
    kiwi = _get_kiwi()

    years = sorted(
        int(p.stem) for p in args.in_dir.glob("*.parquet")
    ) or sorted(int(p.stem) for p in args.in_dir.glob("*.csv"))

    if not years:
        raise SystemExit(f"{args.in_dir}에 연도별 파일이 없다. 먼저 01_extract.py를 실행할 것.")

    year_totals = {}
    t0 = time.time()

    for year in years:
        df = _read_year_sentences(args.in_dir, year)
        if df is None or df.empty:
            continue

        n = min(args.max_per_year, len(df))
        sample = df.sample(n=n, random_state=args.seed)["sentence"]

        counts, total_tokens = tokenize_year(kiwi, sample, stopwords)
        year_totals[year] = total_tokens

        out_path = args.out_dir / f"{year}_counts.parquet"
        counts_df = counts.rename_axis("word").reset_index()
        try:
            counts_df.to_parquet(out_path, index=False)
        except (ImportError, ValueError):
            counts_df.to_csv(args.out_dir / f"{year}_counts.csv", index=False)

        print(
            f"[{year}] 샘플 {n:,}문장 -> 명사 {len(counts):,}종 / 총 어절수 {total_tokens:,}  "
            f"({time.time()-t0:.0f}s 누적)"
        )

    totals_df = pd.DataFrame(
        {"year": list(year_totals.keys()), "total_tokens": list(year_totals.values())}
    ).sort_values("year")
    totals_path = args.out_dir / "year_totals.parquet"
    try:
        totals_df.to_parquet(totals_path, index=False)
    except (ImportError, ValueError):
        totals_df.to_csv(args.out_dir / "year_totals.csv", index=False)

    print(f"완료 -> {args.out_dir}")


if __name__ == "__main__":
    main()

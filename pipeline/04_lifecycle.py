"""
04_lifecycle.py
=================
연도x단어 per-million 행렬에서 단어별 생애주기(birth/peak/death/sharpness/status/total_freq)를
산출해 앱과 소통하는 유일한 파일, data/word_lifecycle.parquet 로 저장한다.

컬럼 정의 (절대 이름/의미를 바꾸지 말 것 - app/ 쪽이 이 이름으로 읽는다):
    word          str    단어
    birth_year    int    처음 등장한 해
    peak_year     int    정점을 찍은 해
    peak_value    float  정점에서의 상대빈도 (per million, 원시 카운트 아님)
    death_year    int/null  사라진 해. 아직 쓰이면 null (0이 아님)
    status        str    alive / declining / dormant
    sharpness     float  peak_value / mean(해당 단어가 등장한 연도들의 per_million)
    total_freq    int    전체 누적 원시 빈도

sharpness가 핵심이다: '인공지능'처럼 꾸준히 쓰이는 단어는 mean이 커서 sharpness가
낮고(시대를 특정 못함), '삐삐'처럼 등장한 몇 해에만 몰려 있는 단어는 mean이 작아
sharpness가 커진다(특정 시기를 강하게 가리킴). 나이 추정 시 가중치로 쓰인다.

status 판정 (참고용 기본 규칙 - 필요하면 조정할 것):
    - death_year가 있으면(마지막 등장 후 더는 관측되지 않으면)      -> dormant
    - 없고, 정점이 최근 RECENT_WINDOW년 안이면                     -> alive
    - 없지만 정점이 오래 전이면(꾸준하지만 화제성은 식음)            -> declining

실행:
    python pipeline/04_lifecycle.py --matrix data/matrix/word_year_permillion.parquet \
        --out data/word_lifecycle.parquet
"""

from __future__ import annotations

import argparse
import pathlib

import pandas as pd

RECENT_WINDOW = 3


def _status(row: pd.Series, last_year: int) -> str:
    if pd.notna(row["death_year"]):
        return "dormant"
    if row["peak_year"] >= last_year - RECENT_WINDOW + 1:
        return "alive"
    return "declining"


def build_lifecycle(matrix: pd.DataFrame) -> pd.DataFrame:
    """long-format (year, word, count, per_million) -> word_lifecycle DataFrame"""
    last_year = int(matrix["year"].max())

    grouped = matrix.groupby("word")
    birth_year = grouped["year"].min()
    last_seen_year = grouped["year"].max()
    total_freq = grouped["count"].sum()

    # peak: 단어별로 per_million이 최대인 연도/값
    idx_peak = grouped["per_million"].idxmax()
    peak_rows = matrix.loc[idx_peak, ["word", "year", "per_million"]].set_index("word")
    peak_year = peak_rows["year"]
    peak_value = peak_rows["per_million"]

    # sharpness = peak / mean(해당 단어가 등장한 연도들의 per_million만 평균)
    mean_per_million = grouped["per_million"].mean()
    sharpness = peak_value / mean_per_million

    death_year = last_seen_year.where(last_seen_year < last_year, other=pd.NA)

    lifecycle = pd.DataFrame({
        "word": birth_year.index,
        "birth_year": birth_year.values,
        "peak_year": peak_year.reindex(birth_year.index).values,
        "peak_value": peak_value.reindex(birth_year.index).values,
        "death_year": death_year.reindex(birth_year.index).values,
        "sharpness": sharpness.reindex(birth_year.index).values,
        "total_freq": total_freq.reindex(birth_year.index).values,
    })

    lifecycle["death_year"] = lifecycle["death_year"].astype("Int64")
    lifecycle["status"] = lifecycle.apply(lambda r: _status(r, last_year), axis=1)

    lifecycle = lifecycle[[
        "word", "birth_year", "peak_year", "peak_value",
        "death_year", "status", "sharpness", "total_freq",
    ]]
    return lifecycle.sort_values("word").reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", default=pathlib.Path("data/matrix/word_year_permillion.parquet"), type=pathlib.Path)
    ap.add_argument("--out", default=pathlib.Path("data/word_lifecycle.parquet"), type=pathlib.Path)
    args = ap.parse_args()

    if args.matrix.exists():
        matrix = pd.read_parquet(args.matrix)
    else:
        csv_fallback = args.matrix.with_suffix(".csv")
        if not csv_fallback.exists():
            raise SystemExit(f"{args.matrix}가 없다. 먼저 03_matrix.py를 실행할 것.")
        matrix = pd.read_csv(csv_fallback)

    lifecycle = build_lifecycle(matrix)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        lifecycle.to_parquet(args.out, index=False)
        print(f"완료: {len(lifecycle):,}개 단어 -> {args.out}")
    except (ImportError, ValueError):
        csv_out = args.out.with_suffix(".csv")
        lifecycle.to_csv(csv_out, index=False)
        print(f"[skip] parquet 저장 실패 -> {csv_out}로 대체 저장. `pip install pyarrow` 후 재실행 권장.")


if __name__ == "__main__":
    main()

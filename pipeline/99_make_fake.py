"""
99_make_fake.py
================
앱 개발용 더미 word_lifecycle 데이터를 생성한다.

확정된 스키마(8컬럼)와 100% 동일한 parquet 파일을 만들기 때문에, 앱은 이 파일과
진짜 파이프라인 산출물을 구분하지 못한다. 진짜 데이터가 준비되면 이 파일 위에
그대로 덮어쓰면 된다 (컬럼 이름/타입/의미를 절대 바꾸지 말 것).

실행:
    python pipeline/99_make_fake.py

출력:
    data/word_lifecycle.parquet   (pyarrow 설치 시)
    data/word_lifecycle.csv       (항상 생성 - parquet 엔진이 없는 환경 대비 fallback.
                                    app.py는 parquet가 없으면 csv를 자동으로 읽는다)
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

ANALYSIS_FIRST_YEAR = 2009
ANALYSIS_LAST_YEAR = 2024  # 정찰 결과: 2009~2024, 공백 없음
RECENT_WINDOW = 3          # 최근 N년 이내에 정점/활동이 있으면 'alive' 취급

OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------------------
# 1) 큐레이션 단어 - config/question_bank.yaml의 모든 선택지가 반드시 여기 포함되어야
#    질문에 답했을 때 앱이 실제로 단어를 찾아낼 수 있다.
#    (word, birth_year, peak_year, death_year 또는 None, sharpness, peak_value, total_freq)
# ---------------------------------------------------------------------------
CURATED = [
    # --- 어릴 때 쓰던 물건 (q1) ---
    ("삐삐",        2009, 2016, 2021,   4.8,   12.0,     45_000),
    ("시티폰",      2010, 2015, 2019,   5.2,    8.0,     21_000),
    ("엠피쓰리",    2009, 2010, 2017,   3.6,   20.0,     25_000),
    ("폴더폰",      2009, 2011, 2019,   3.7,   40.0,     55_000),
    ("스마트폰",    2009, 2013, None,   1.41, 320.0,  15_000_000),

    # --- 초등학생 때 유행 (q2) ---
    ("다마고치",    2009, 2018, None,   3.9,   15.0,     38_000),
    ("미니홈피",    2009, 2010, 2018,   4.5,   45.0,     90_000),
    ("마인크래프트",2011, 2020, None,   2.6,  140.0,    900_000),
    ("챌린지",      2015, 2021, None,   2.1,  180.0,  1_100_000),

    # --- 학창 시절 패션 (q3) ---
    ("스키니진",    2009, 2012, 2019,   3.0,   30.0,     40_000),
    ("크롭티",      2009, 2023, None,   3.2,   55.0,     70_000),
    ("롱패딩",      2016, 2018, 2022,   4.4,   65.0,     80_000),
    ("슬리퍼",      2009, 2019, None,   1.8,   50.0,    150_000),

    # --- 학창 시절 메신저 (q4) ---
    ("세이클럽",    2009, 2012, 2020,   4.1,   25.0,     60_000),
    ("네이트온",    2009, 2011, 2017,   3.5,   60.0,    200_000),
    ("카카오톡",    2010, 2015, None,   1.6,  400.0,  9_000_000),
    ("인스타그램",  2011, 2021, None,   2.0,  500.0,  7_000_000),

    # --- 유행어/신조어 (q5) ---
    ("안습",        2009, 2011, 2016,   4.2,   18.0,     22_000),
    ("즐",          2009, 2010, 2015,   3.8,   10.0,     12_000),
    ("인싸",        2018, 2019, None,   4.6,   60.0,     85_000),
    ("오운완",      2020, 2022, None,   3.9,   25.0,     30_000),
    ("갓생",        2021, 2023, None,   4.3,   35.0,     40_000),

    # --- 최근 관심사 (q6) ---
    ("챗지피티",    2022, 2023, None,   6.41, 850.0,  1_200_000),
    ("메타버스",    2021, 2022, None,   5.5,  300.0,    500_000),
    ("유튜브",      2009, 2020, None,   1.8,  600.0, 12_000_000),
    ("숏폼",        2021, 2024, None,   3.4,  220.0,    260_000),
]

CURATED_COLUMNS = [
    "word", "birth_year", "peak_year", "death_year",
    "sharpness", "peak_value", "total_freq",
]

# ---------------------------------------------------------------------------
# 2) 필러 단어 - 스트림그래프를 풍성하게 보여주기 위한 배경 단어들.
#    질문뱅크와는 무관하지만, 실제 데이터가 들어왔을 때의 분포(수백~수천 단어)를
#    흉내내기 위해 무작위로 생성한다.
# ---------------------------------------------------------------------------
FILLER_SEED_WORDS = [
    "싸이월드", "버디버디", "아이러브스쿨", "미투데이", "판도라티비",
    "닌텐도DS", "아이팟", "갤럭시", "아이폰", "넷플릭스",
    "재택근무", "코로나", "마스크", "위드코로나", "챗봇",
    "인공지능", "반려동물", "캠핑", "홈트", "골프",
    "부캐", "밈", "짤방", "케미", "치맥",
    "혼밥", "혼술", "가성비", "플렉스", "소확행",
    "워라밸", "탕진잼", "복세편살", "존버", "빚투",
    "영끌", "무지출챌린지", "디토소비", "가심비", "럭키비키",
]


def _rng(seed: int = 20260721) -> np.random.Generator:
    return np.random.default_rng(seed)


def _make_filler_rows(rng: np.random.Generator) -> list[tuple]:
    rows = []
    for word in FILLER_SEED_WORDS:
        birth_year = int(rng.integers(ANALYSIS_FIRST_YEAR, ANALYSIS_LAST_YEAR - 1))
        peak_year = int(rng.integers(birth_year, ANALYSIS_LAST_YEAR + 1))

        # 40% 확률로 이미 죽은 단어 (death_year 존재), 나머지는 아직 쓰이는 중(null)
        is_dormant = rng.random() < 0.4
        if is_dormant and peak_year < ANALYSIS_LAST_YEAR:
            death_year = int(rng.integers(peak_year + 1, ANALYSIS_LAST_YEAR + 1))
        else:
            death_year = None

        sharpness = float(np.clip(rng.lognormal(mean=1.0, sigma=0.5), 1.05, 9.0))
        peak_value = float(rng.uniform(5, 400))
        total_freq = int(rng.integers(5_000, 3_000_000))

        rows.append((word, birth_year, peak_year, death_year, sharpness, peak_value, total_freq))
    return rows


def _status_from_row(row: pd.Series) -> str:
    """death_year/peak_year를 근거로 alive / declining / dormant 를 판정한다.

    - death_year가 있으면(더 이상 관측되지 않으면) 'dormant'
    - death_year가 없고, 정점이 최근 RECENT_WINDOW년 안에 있으면 'alive'
    - death_year가 없지만 정점이 오래 전이면(꾸준히 쓰이지만 화제성은 식음) 'declining'
    """
    if pd.notna(row["death_year"]):
        return "dormant"
    if row["peak_year"] >= ANALYSIS_LAST_YEAR - RECENT_WINDOW + 1:
        return "alive"
    return "declining"


def build_dataframe(seed: int = 20260721) -> pd.DataFrame:
    """확정 스키마의 word_lifecycle DataFrame을 만든다. (테스트에서 재사용 가능)"""
    rng = _rng(seed)

    curated_rows = [dict(zip(CURATED_COLUMNS, r)) for r in CURATED]
    filler_rows = [dict(zip(CURATED_COLUMNS, r)) for r in _make_filler_rows(rng)]

    df = pd.DataFrame(curated_rows + filler_rows)

    # status는 큐레이션 단어도 동일한 규칙으로 재계산해 일관성을 보장한다.
    df["death_year"] = df["death_year"].astype("Int64")
    df["status"] = df.apply(_status_from_row, axis=1)

    df["birth_year"] = df["birth_year"].astype(int)
    df["peak_year"] = df["peak_year"].astype(int)
    df["peak_value"] = df["peak_value"].astype(float)
    df["sharpness"] = df["sharpness"].astype(float)
    df["total_freq"] = df["total_freq"].astype(int)

    # 최종 컬럼 순서를 스펙과 동일하게 고정
    df = df[[
        "word", "birth_year", "peak_year", "peak_value",
        "death_year", "status", "sharpness", "total_freq",
    ]]

    assert (df["birth_year"] <= df["peak_year"]).all(), "birth_year는 peak_year보다 늦을 수 없다"
    assert df["word"].is_unique, "중복 단어가 있다"

    return df.sort_values("word").reset_index(drop=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = build_dataframe()

    csv_path = OUT_DIR / "word_lifecycle.csv"
    df.to_csv(csv_path, index=False)
    print(f"[ok] {csv_path}  ({len(df)}개 단어)")

    parquet_path = OUT_DIR / "word_lifecycle.parquet"
    try:
        df.to_parquet(parquet_path, index=False)
        print(f"[ok] {parquet_path}")
    except (ImportError, ValueError) as e:
        print(
            "[skip] parquet 저장 실패 (pyarrow/fastparquet 미설치로 추정): "
            f"{e}\n       -> csv만 생성됨. `pip install pyarrow` 후 다시 실행하면 parquet도 생성됩니다."
        )

    print("\n검증용 요약 (문서의 더미 실행 결과와 비교):")
    check = df[df["word"].isin(["챗지피티", "스마트폰"])][["word", "sharpness"]]
    print(check.to_string(index=False))


if __name__ == "__main__":
    main()

# CLAUDE.md

이 문서는 프로젝트 소개가 아니라 **이 저장소에서 작업할 때 지켜야 할 규칙**을 담는다.
프로젝트 개요는 README.md 참고.

## 1. pipeline/ 과 app/ 은 절대 섞지 않는다

- `pipeline/` = 오프라인 배치. 말뭉치(수십 GB)를 읽어 `data/word_lifecycle.parquet`(+ `.csv` 폴백)
  하나로 압축하는 것이 유일한 목적이다. `01_extract.py → 02_tokenize.py → 03_matrix.py → 04_lifecycle.py`
  순서로 실행하며, 각 단계는 이전 단계의 산출물 파일 존재 여부만으로 이어서 실행 가능해야 한다.
- `app/` = Streamlit 앱. **오직 `data/word_lifecycle.parquet`(없으면 `.csv`)만 읽는다.**
  앱 코드에서 `pipeline/`의 함수를 import 하거나, 말뭉치 원본(`data/raw/`)을 직접 열거나,
  파이프라인 스크립트를 subprocess로 호출하는 코드를 추가하지 말 것 — 앱은 항상 "이미 계산된
  결과를 읽기만" 해야 한다.
- **주의 (README와의 불일치)**: README.md는 앱이 `data/processed/`를 읽는다고 설명하지만,
  실제 `app/app.py`의 `DATA_DIR`은 저장소 루트의 `data/` 이고 `04_lifecycle.py` `--out`
  기본값도 `data/word_lifecycle.parquet`이다(즉 `data/processed/`가 아니라 `data/` 바로 아래).
  둘 중 하나로 통일하기 전까지는 **코드(`app/app.py`의 `DATA_DIR`)를 기준**으로 판단하고,
  임의로 경로를 `data/processed/`로 옮기지 말 것 — 옮기려면 `app/app.py`와
  `pipeline/04_lifecycle.py`의 기본 `--out`을 함께 바꿔야 한다.

## 2. 실행 명령어

```bash
pip install -r requirements.txt
streamlit run app/app.py
```

(README와 최초 요청에는 `app/main.py`로 되어 있으나, 실제 진입점 파일은 `app/app.py`이다.
`app/main.py`는 존재하지 않으므로 이 이름으로 안내하거나 새로 만들지 말 것.)

## 3. data/raw/ 원본 말뭉치

- `data/raw/`, `data/interim/`은 `.gitignore`에 의해 커밋 금지 처리되어 있다 (국립국어원
  「모두의 말뭉치」 원문, 저작권상 재배포 불가).
- 이 폴더 안의 파일을 `git add`하거나, README/문서에 원문 내용을 그대로 인용해 옮겨 적거나,
  다른 곳(이슈, PR, 외부 서비스)에 업로드하지 말 것. 통계·시각화 결과만 공개 대상이다.
- 파일명 연도와 문서 내부 실제 날짜가 다를 수 있음이 이미 확인된 사실이다
  (`01_extract.py`도 파일명이 아니라 문서 내부 `date` 필드만 신뢰하도록 작성돼 있음).
  말뭉치 관련 스크립트를 수정할 때 이 전제를 깨지 말 것.

## 4. 산출물이 진짜 배치 결과인지 더미인지 구분하는 법

`pipeline/99_make_fake.py`가 만든 더미 데이터와 실제 파이프라인 산출물은 스키마(8컬럼)가
100% 동일해서 앱은 구분하지 못한다. 확인이 필요하면:

1. **하드코딩 리터럴 대조**: `99_make_fake.py`의 `CURATED` 리스트에 있는 값과 정확히 일치하면
   더미다. 예: `챗지피티` 행이 `birth_year=2022, peak_year=2023, peak_value=850.0,
   sharpness=6.41, total_freq=1_200_000`과 정확히 같으면 100% 더미 (실제 계산값은 이렇게
   딱 떨어지는 소수점을 갖지 않는다).
2. **중간 산출물 존재 여부**: 실제 파이프라인을 돌렸다면 `data/extracted/`, `data/tokenized/`,
   (경로 통일 전이라면) `data/matrix/`에 연도별 중간 파일이 남아 있어야 한다. 이게 없이
   `data/word_lifecycle.*`만 있다면 `99_make_fake.py`로 만든 더미일 가능성이 높다.
3. **연도 커버리지**: 실제 산출물은 `birth_year`/`peak_year`가 2009~2024 전 연도에 걸쳐
   고르게 분포한다(샘플 실행이면 그보다 좁음). 더미는 `FILLER_SEED_WORDS`의 무작위 생성
   특성상 분포가 그럴듯해 보이지만 `CURATED` 단어들의 값은 위 1번 기준으로 항상 걸러낸다.

## 5. 파이프라인 핵심 상수 위치

| 상수 | 위치 | 의미 |
|---|---|---|
| `FIRST_YEAR` / `LAST_YEAR` (2009 / 2024) | `pipeline/01_extract.py`, `pipeline/99_make_fake.py`(`ANALYSIS_FIRST_YEAR`/`ANALYSIS_LAST_YEAR`로 중복 정의) | 분석 대상 연도 범위. 두 파일에 중복돼 있으니 바꿀 때 같이 바꿀 것. |
| `DEFAULT_MAX_PER_YEAR` (300_000) | `pipeline/02_tokenize.py` | 연도당 Kiwi로 처리할 문장 샘플 상한. 전체(28.5GB)를 그대로 돌리면 하루 이상 걸려서 검증용으로 낮춰둔 값이다. 실 서비스용 최종 실행은 `--max-per-year 1000000`으로 늘려서 돌려야 한다(주석에 명시돼 있음). |
| `CSV_CHUNKSIZE` (200_000) | `pipeline/01_extract.py` | CSV를 청크 단위로 읽어 28.5GB를 한 번에 메모리에 올리지 않기 위한 값. |
| `RECENT_WINDOW` (3) | `pipeline/04_lifecycle.py`, `pipeline/99_make_fake.py` | 정점 연도가 `마지막 연도 - RECENT_WINDOW + 1` 이후면 `alive`로 분류. |

## 6. 코딩 스타일

기존 코드(`pipeline/*.py`, `app/*.py`)의 스타일을 그대로 따른다. 새로운 컨벤션을 도입하지 말 것.

- 모든 파일 상단에 `from __future__ import annotations`.
- 함수 시그니처에는 타입힌트를 붙인다(`def foo(path: pathlib.Path) -> pd.DataFrame:`).
- docstring은 모듈 상단에 하나만 (역할 + 실행 명령 예시). 개별 함수에는 굳이 docstring을
  달지 않고, 필요하면 한 줄 주석으로 충분하다. 여러 줄짜리 함수 docstring을 새로 추가하지 말 것.
- `data/word_lifecycle.parquet`의 8개 컬럼(`word, birth_year, peak_year, peak_value,
  death_year, status, sharpness, total_freq`)의 이름·의미·타입은 app과의 계약이므로
  임의로 바꾸지 말 것 (바꾸려면 `04_lifecycle.py`, `99_make_fake.py`, `app/app.py`를 동시에 수정).

"""
estimator.py
=============
나이 추정 로직 (프로젝트의 핵심).

    추정_출생연도 = 단어의 peak_year - 질문의 implicit_age
    가중치        = sharpness x 질문 confidence

    가중 중앙값   -> 최종 추정 출생연도
    25~75 백분위  -> "1998~2001년생" 같은 범위
    언어 나이     = 올해 - 추정 출생연도

추정 근거를 전부 공개하는 것이 심리테스트와의 결정적 차이다. 결과에 범위가 나오는
이유는 추정치들이 흩어지기 때문이며, 그 흩어짐 자체가 정직한 통계다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Evidence:
    question_id: str
    word: str
    implicit_age: int
    confidence: float
    source: str  # 'choice' | 'text'


@dataclass
class EstimationResult:
    estimated_birth_year: int
    birth_year_low: int
    birth_year_high: int
    language_age: int
    evidence_table: pd.DataFrame = field(repr=False)


def weighted_percentile(values: list[float], weights: list[float], q: float) -> float:
    """0~100 사이 q번째 가중 백분위수. (값, 가중치) 쌍을 값 기준 정렬 후 누적가중치로 계산."""
    if not values:
        raise ValueError("values가 비어 있다")

    pairs = sorted(zip(values, weights), key=lambda p: p[0])
    sorted_values = [v for v, _ in pairs]
    sorted_weights = [w for _, w in pairs]

    total_weight = sum(sorted_weights)
    if total_weight <= 0:
        # 가중치가 전부 0이면 단순 평균으로 대체
        return sum(sorted_values) / len(sorted_values)

    cum_weight = 0.0
    target = (q / 100.0) * total_weight
    for value, weight in zip(sorted_values, sorted_weights):
        cum_weight += weight
        if cum_weight >= target:
            return value
    return sorted_values[-1]


def build_evidence(
    lifecycle_df: pd.DataFrame, raw_evidence: list[Evidence]
) -> pd.DataFrame:
    """Evidence 목록 -> word_lifecycle 조회 결과가 합쳐진 근거 테이블."""
    lookup = lifecycle_df.set_index("word")

    rows = []
    for ev in raw_evidence:
        if ev.word not in lookup.index:
            continue
        row = lookup.loc[ev.word]
        peak_year = int(row["peak_year"])
        sharpness = float(row["sharpness"])
        candidate_birth_year = peak_year - ev.implicit_age
        weight = sharpness * ev.confidence

        rows.append({
            "question_id": ev.question_id,
            "word": ev.word,
            "source": ev.source,
            "peak_year": peak_year,
            "sharpness": round(sharpness, 2),
            "implicit_age": ev.implicit_age,
            "confidence": ev.confidence,
            "candidate_birth_year": candidate_birth_year,
            "weight": round(weight, 3),
        })

    return pd.DataFrame(rows)


def estimate(
    lifecycle_df: pd.DataFrame,
    raw_evidence: list[Evidence],
    current_year: int,
) -> EstimationResult | None:
    """근거가 하나도 없으면 None을 반환한다 (앱에서 안내 메시지 처리)."""
    evidence_table = build_evidence(lifecycle_df, raw_evidence)
    if evidence_table.empty:
        return None

    evidence_table = evidence_table.sort_values("weight", ascending=False).reset_index(drop=True)

    values = evidence_table["candidate_birth_year"].tolist()
    weights = evidence_table["weight"].tolist()

    median = weighted_percentile(values, weights, 50)
    low = weighted_percentile(values, weights, 25)
    high = weighted_percentile(values, weights, 75)

    estimated_birth_year = round(median)
    birth_year_low = round(min(low, high))
    birth_year_high = round(max(low, high))
    language_age = current_year - estimated_birth_year

    return EstimationResult(
        estimated_birth_year=estimated_birth_year,
        birth_year_low=birth_year_low,
        birth_year_high=birth_year_high,
        language_age=language_age,
        evidence_table=evidence_table,
    )

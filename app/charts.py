"""
charts.py
==========
세 가지 시각화를 만든다.
    1) streamgraph()       전체 단어의 생애주기를 스트림그래프로
    2) my_words_chart()    사용자가 답한 단어들이 추정에 기여한 정도
    3) life_stage_bands()  추정 출생연도를 기준으로 인생 시기를 연도축에 배치

주의: word_lifecycle.parquet는 파이프라인과 앱이 합의한 유일한 소통 파일이며,
연도별 원시 시계열(연도x단어 행렬)은 포함하지 않는다(용량 문제 + 스키마 단순화).
따라서 streamgraph는 birth_year/peak_year/death_year/peak_value/sharpness만으로
'그럴듯한' 생애주기 곡선을 재구성한 근사치다. 실제 연도별 빈도 곡선이 아니라
생애주기의 형태를 보여주기 위한 시각화임을 화면에 함께 안내한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

LIFE_STAGES = [
    ("유아기", 0, 6, "#FDE68A"),
    ("아동기", 7, 12, "#FCA5A5"),
    ("청소년기", 13, 18, "#93C5FD"),
    ("청년기", 19, 29, "#6EE7B7"),
    ("장년기", 30, 49, "#C4B5FD"),
    ("중장년기", 50, 64, "#F9A8D4"),
    ("노년기", 65, 100, "#D1D5DB"),
]


def _reconstruct_series(row: pd.Series, years: list[int]) -> np.ndarray:
    """단어 한 개의 생애주기 요약값 -> 연도별 근사 곡선 (triangular ramp up/down)."""
    birth_year = int(row["birth_year"])
    peak_year = int(row["peak_year"])
    peak_value = float(row["peak_value"])
    death_year = row["death_year"]
    status = row["status"]
    last_year = years[-1]

    if pd.notna(death_year):
        end_year = int(death_year)
        end_value = peak_value * 0.03
    else:
        end_year = last_year
        end_value = peak_value * (0.35 if status == "alive" else 0.15)

    start_value = peak_value * 0.02

    values = np.zeros(len(years), dtype=float)
    for i, year in enumerate(years):
        if year < birth_year or year > end_year:
            values[i] = 0.0
        elif year <= peak_year:
            span = max(peak_year - birth_year, 1)
            frac = (year - birth_year) / span
            values[i] = start_value + frac * (peak_value - start_value)
        else:
            span = max(end_year - peak_year, 1)
            frac = (year - peak_year) / span
            values[i] = peak_value + frac * (end_value - peak_value)
    return values


def streamgraph(
    lifecycle_df: pd.DataFrame,
    highlight_words: list[str] | None = None,
    top_n: int = 25,
) -> go.Figure:
    highlight_words = highlight_words or []
    years = list(range(int(lifecycle_df["birth_year"].min()), int(lifecycle_df["peak_year"].max()) + 1))

    top_words_df = lifecycle_df.sort_values("total_freq", ascending=False).head(top_n)
    show_words = set(top_words_df["word"]) | set(highlight_words)
    subset = lifecycle_df[lifecycle_df["word"].isin(show_words)].copy()
    # 시각적 흐름이 자연스럽도록 정점 연도 순으로 정렬
    subset = subset.sort_values("peak_year").reset_index(drop=True)

    series = {row["word"]: _reconstruct_series(row, years) for _, row in subset.iterrows()}
    stack = np.vstack(list(series.values())) if series else np.zeros((0, len(years)))

    baseline = -stack.sum(axis=0) / 2.0
    cum = baseline.copy()

    fig = go.Figure()
    for word, values in series.items():
        top = cum + values
        is_highlighted = word in highlight_words
        fig.add_trace(go.Scatter(
            x=years + years[::-1],
            y=list(top) + list(cum[::-1]),
            fill="toself",
            mode="lines",
            line=dict(width=0.5, color="#F97316" if is_highlighted else "#94A3B8"),
            fillcolor="rgba(249,115,22,0.85)" if is_highlighted else "rgba(148,163,184,0.35)",
            name=word,
            hovertemplate=f"{word}<br>연도 %{{x}}<extra></extra>",
        ))
        cum = top

    fig.update_layout(
        title="단어 생애주기 스트림그래프 (근사 재구성 · 굵고 진한 색 = 내가 답한 단어)",
        showlegend=False,
        xaxis_title="연도",
        yaxis=dict(showticklabels=False, title=""),
        margin=dict(l=10, r=10, t=50, b=10),
        height=420,
    )
    return fig


def my_words_chart(evidence_table: pd.DataFrame) -> go.Figure:
    df = evidence_table.sort_values("weight", ascending=True)
    fig = go.Figure(go.Bar(
        x=df["weight"],
        y=df["word"],
        orientation="h",
        marker_color="#F97316",
        text=[f"{y}년 정점 · sharpness {s}" for y, s in zip(df["peak_year"], df["sharpness"])],
        textposition="outside",
        hovertemplate="%{y}<br>가중치 %{x:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="내 단어가 추정에 기여한 정도 (가중치 = sharpness x 질문 신뢰도)",
        xaxis_title="가중치",
        yaxis_title="",
        margin=dict(l=10, r=10, t=50, b=10),
        height=90 + 40 * len(df),
    )
    return fig


def life_stage_bands(estimated_birth_year: int, low: int, high: int, current_year: int) -> go.Figure:
    fig = go.Figure()

    for name, age_start, age_end, color in LIFE_STAGES:
        year_start = estimated_birth_year + age_start
        year_end = estimated_birth_year + age_end
        if year_start > current_year:
            continue
        year_end = min(year_end, current_year)
        fig.add_trace(go.Bar(
            x=[year_end - year_start],
            base=[year_start],
            y=["인생 시기"],
            orientation="h",
            marker_color=color,
            name=name,
            text=name,
            textposition="inside",
            hovertemplate=f"{name} ({age_start}~{age_end}세) · {year_start}~{year_end}년<extra></extra>",
        ))

    # 25~75 백분위 불확실성 구간을 얇은 마커로 함께 표시
    fig.add_vrect(x0=low, x1=high, fillcolor="black", opacity=0.08, line_width=0)
    fig.add_vline(x=estimated_birth_year, line_dash="dash", line_color="black")

    fig.update_layout(
        title=f"추정 출생연도({estimated_birth_year}년) 기준 인생 시기 · 음영 = 25~75% 추정 범위({low}~{high}년)",
        barmode="stack",
        showlegend=True,
        xaxis_title="연도",
        yaxis=dict(showticklabels=False, title=""),
        margin=dict(l=10, r=10, t=50, b=10),
        height=220,
    )
    return fig

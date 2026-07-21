"""
questions.py
=============
config/question_bank.yaml을 읽어 Streamlit 위젯으로 렌더링하고, 답변을
estimator.Evidence로 변환하기 직전 단계의 raw response 딕셔너리로 모은다.
"""

from __future__ import annotations

import pathlib

import streamlit as st
import yaml


def load_question_bank(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def render_questions(question_bank: dict) -> list[dict]:
    """각 질문을 st 위젯으로 그리고, 답변을 모아서 반환한다.

    반환 형식: [{id, type, implicit_age, confidence, word=None, raw_text=None}, ...]
    선택하지 않은 객관식이나 빈 서술형은 결과 목록에서 제외되지 않고 그대로 담기며,
    이후 app.py에서 word/raw_text가 비어있는 항목을 걸러낸다.
    """
    responses: list[dict] = []

    choice_questions = [q for q in question_bank["questions"] if q["type"] == "choice"]
    text_questions = [q for q in question_bank["questions"] if q["type"] == "text"]

    st.subheader("객관식")
    for q in choice_questions:
        labels = [opt["label"] for opt in q["options"]]
        choice = st.radio(q["text"], labels, index=None, key=f"choice_{q['id']}")
        word = None
        if choice is not None:
            word = next(opt["word"] for opt in q["options"] if opt["label"] == choice)
        responses.append({
            "id": q["id"],
            "type": "choice",
            "implicit_age": q["implicit_age"],
            "confidence": q["confidence"],
            "word": word,
            "raw_text": None,
        })

    st.subheader("서술형")
    for q in text_questions:
        text = st.text_input(
            q["text"], key=f"text_{q['id']}", placeholder=q.get("placeholder", "")
        )
        responses.append({
            "id": q["id"],
            "type": "text",
            "implicit_age": q["implicit_age"],
            "confidence": q["confidence"],
            "word": None,
            "raw_text": text,
        })

    return responses

"""
app.py
=======
언어 나이 진단기 - Streamlit 진입점.

    streamlit run app/app.py

data/word_lifecycle.parquet (없으면 .csv) 를 읽어 질문을 던지고, 답변에서 나온
단어들의 생애주기를 근거로 언어 나이를 추정해 보여준다. 파이프라인이 진짜 데이터를
만들기 전까지는 pipeline/99_make_fake.py가 만든 더미 데이터로 완전히 동작한다.

화면은 st.session_state["stage"]로 quiz / result 두 단계를 완전히 분리한다.
진단 버튼을 누르면 quiz 화면 대신 result 화면 전체가 렌더링되고,
"다시 해보기"를 누르면 답변이 초기화되며 quiz 화면으로 돌아간다.
"""

from __future__ import annotations

import datetime
import pathlib

import pandas as pd
import streamlit as st

import charts
import estimator
import matcher
import questions

APP_DIR = pathlib.Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
DATA_DIR = ROOT_DIR / "data"
CONFIG_DIR = ROOT_DIR / "config"

CURRENT_YEAR = datetime.date.today().year

SOURCE_LABELS = {"choice": "선택형", "text": "서술형"}


@st.cache_data
def load_lifecycle() -> pd.DataFrame | None:
    parquet_path = DATA_DIR / "word_lifecycle.parquet"
    csv_path = DATA_DIR / "word_lifecycle.csv"
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except (ImportError, ValueError):
            pass
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df["death_year"] = df["death_year"].astype("Int64")
        return df
    return None


@st.cache_data
def load_question_bank() -> dict:
    return questions.load_question_bank(CONFIG_DIR / "question_bank.yaml")


def build_evidence(responses: list[dict], vocab: set[str]) -> list[estimator.Evidence]:
    evidence: list[estimator.Evidence] = []
    for r in responses:
        if r["type"] == "choice" and r["word"]:
            evidence.append(estimator.Evidence(
                question_id=r["id"], word=r["word"],
                implicit_age=r["implicit_age"], confidence=r["confidence"], source="choice",
            ))
        elif r["type"] == "text" and r["raw_text"]:
            for word in matcher.extract_words(r["raw_text"], vocab):
                evidence.append(estimator.Evidence(
                    question_id=r["id"], word=word,
                    implicit_age=r["implicit_age"], confidence=r["confidence"], source="text",
                ))
    return evidence


def init_state() -> None:
    st.session_state.setdefault("stage", "quiz")
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("responses", None)


def reset_quiz(qbank: dict) -> None:
    """답변 위젯 상태를 전부 지우고 quiz 화면으로 되돌린다."""
    for q in qbank["questions"]:
        key = f"choice_{q['id']}" if q["type"] == "choice" else f"text_{q['id']}"
        st.session_state.pop(key, None)
    st.session_state["stage"] = "quiz"
    st.session_state["result"] = None
    st.session_state["responses"] = None


def render_quiz(lifecycle_df: pd.DataFrame, qbank: dict, vocab: set[str]) -> None:
    st.title("🕰️ 언어 나이 진단기")
    st.caption("당신은 나이를 말하지 않았다. 당신의 단어가 말했다.")

    backend = matcher.get_backend_name()
    if backend == "simple":
        st.info(
            "형태소 분석기(kiwipiepy)가 설치되어 있지 않아 서술형 답변은 간이 매칭(부분 문자열 대조)으로 "
            "처리됩니다. 더 정확한 결과를 원하면 `pip install kiwipiepy` 후 다시 실행하세요.",
            icon="ℹ️",
        )

    responses = questions.render_questions(qbank)

    if st.button("내 언어 나이 진단하기", type="primary"):
        evidence = build_evidence(responses, vocab)
        result = estimator.estimate(lifecycle_df, evidence, current_year=CURRENT_YEAR)

        if result is None:
            st.warning("답변에서 사전에 등록된 단어를 찾지 못했습니다. 객관식을 최소 1개 이상 선택하거나, 서술형에 조금 더 구체적인 단어를 적어보세요.")
            st.stop()

        st.session_state["result"] = result
        st.session_state["responses"] = responses
        st.session_state["stage"] = "result"
        st.rerun()


def render_result(lifecycle_df: pd.DataFrame, qbank: dict) -> None:
    result: estimator.EstimationResult = st.session_state["result"]
    responses: list[dict] = st.session_state["responses"]

    st.title("🕰️ 언어 나이 진단 결과")
    if st.button("↺ 다시 해보기"):
        reset_quiz(qbank)
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("언어 나이", f"{result.language_age}세")
    with col2:
        st.metric("추정 출생연도", f"{result.estimated_birth_year}년", f"{result.birth_year_low}~{result.birth_year_high}년 범위")

    st.caption(
        "범위가 나오는 이유는 추정치들이 흩어지기 때문이며, 그 흩어짐 자체가 정직한 통계입니다. "
        "아래에서 추정 근거를 전부 확인할 수 있습니다."
    )

    st.subheader("추정 근거")
    display_table = result.evidence_table.copy()
    display_table["source"] = display_table["source"].map(SOURCE_LABELS).fillna(display_table["source"])
    st.dataframe(
        display_table[[
            "word", "source", "peak_year", "sharpness", "implicit_age", "confidence", "weight",
        ]].rename(columns={
            "word": "단어", "source": "출처", "peak_year": "정점 연도", "sharpness": "뾰족함",
            "implicit_age": "암묵 나이", "confidence": "질문 신뢰도", "weight": "가중치",
        }),
        hide_index=True,
        use_container_width=True,
    )

    st.plotly_chart(charts.my_words_chart(result.evidence_table), use_container_width=True)

    st.subheader("전체 단어 생애주기")
    st.plotly_chart(
        charts.streamgraph(lifecycle_df, highlight_words=result.evidence_table["word"].tolist()),
        use_container_width=True,
    )

    st.subheader("내 세대 단어 추천")
    exclude_words = set(result.evidence_table["word"].tolist())
    recommended = estimator.recommend_generation_words(
        lifecycle_df, result.estimated_birth_year, exclude_words,
    )
    if recommended.empty:
        st.caption("이 세대 구간에 추천할 단어가 아직 없어요.")
    else:
        st.caption(f"{result.estimated_birth_year}년생이라면 이런 단어들도 익숙했을 거예요.")
        cols = st.columns(min(len(recommended), 3))
        for i, (_, row) in enumerate(recommended.iterrows()):
            with cols[i % len(cols)]:
                st.metric(row["word"], f"{int(row['peak_year'])}년 정점")

    with st.expander("내가 답한 내용 보기"):
        by_id = {r["id"]: r for r in responses}
        for q in qbank["questions"]:
            r = by_id.get(q["id"])
            if r is None:
                continue
            if r["type"] == "choice":
                answer = r.get("label") or "ـ (선택 안 함)"
            else:
                answer = r["raw_text"] or "ـ (입력 안 함)"
            st.markdown(f"**{q['text']}**  \n{answer}")

    st.divider()
    st.subheader("궁금한 단어의 생애주기 찾아보기")
    st.caption("최대 3개까지 입력해서 곡선을 겹쳐볼 수 있어요. (1개만 입력해도 돼요)")
    col_a, col_b, col_c = st.columns(3)
    w1 = col_a.text_input("단어 1", key="word_lookup_1", placeholder="예: 삐삐")
    w2 = col_b.text_input("단어 2 (선택)", key="word_lookup_2", placeholder="예: 인싸")
    w3 = col_c.text_input("단어 3 (선택)", key="word_lookup_3", placeholder="예: 갓생")

    query_words = [w.strip() for w in (w1, w2, w3) if w.strip()]
    if query_words:
        fig = charts.word_lifecycle_curves(lifecycle_df, query_words, CURRENT_YEAR)
        missing = [w for w in query_words if lifecycle_df[lifecycle_df["word"] == w].empty]
        if fig is None:
            st.warning("입력한 단어가 전부 사전에 없습니다.")
        else:
            st.plotly_chart(fig, use_container_width=True)
            if missing:
                st.caption(f"사전에 없어 제외된 단어: {', '.join(missing)}")


def main() -> None:
    st.set_page_config(page_title="언어 나이 진단기", page_icon="🕰️", layout="centered")
    init_state()

    lifecycle_df = load_lifecycle()
    if lifecycle_df is None:
        st.error(
            "word_lifecycle 데이터를 찾을 수 없습니다.\n\n"
            "터미널에서 `python pipeline/99_make_fake.py`를 먼저 실행해 더미 데이터를 만들어 주세요."
        )
        st.stop()

    vocab = set(lifecycle_df["word"])
    qbank = load_question_bank()

    if st.session_state["stage"] == "result" and st.session_state["result"] is not None:
        render_result(lifecycle_df, qbank)
    else:
        render_quiz(lifecycle_df, qbank, vocab)


if __name__ == "__main__":
    main()
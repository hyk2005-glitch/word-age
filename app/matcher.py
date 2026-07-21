"""
matcher.py
==========
서술형(주관식) 답변 -> 명사 추출 -> word_lifecycle 사전 조회.

kiwipiepy가 설치되어 있으면 형태소 분석으로 명사(NNG/NNP)를 뽑아 사전과 대조한다.
설치되어 있지 않은 환경(개발 중, 데모 등)에서도 앱이 멈추지 않도록, 사전 단어가
텍스트에 부분 문자열로 포함되는지 훑는 간이 매칭으로 자동 대체된다.
어느 쪽이 쓰였는지는 get_backend_name()으로 확인해 앱 화면에 투명하게 표시한다.
"""

from __future__ import annotations

NOUN_TAGS = {"NNG", "NNP"}

_kiwi_instance = None
_kiwi_import_failed = False


def _get_kiwi():
    global _kiwi_instance, _kiwi_import_failed
    if _kiwi_import_failed:
        return None
    if _kiwi_instance is not None:
        return _kiwi_instance
    try:
        from kiwipiepy import Kiwi
        _kiwi_instance = Kiwi()
        return _kiwi_instance
    except ImportError:
        _kiwi_import_failed = True
        return None


def get_backend_name() -> str:
    """'kiwi' 또는 'simple' (kiwipiepy 미설치 시 fallback)"""
    return "kiwi" if _get_kiwi() is not None else "simple"


def _extract_nouns_kiwi(text: str) -> list[str]:
    kiwi = _get_kiwi()
    nouns = []
    for token in kiwi.tokenize(text):
        if token.tag in NOUN_TAGS and len(token.form) >= 2:
            nouns.append(token.form)
    return nouns


def extract_words(text: str, vocab: set[str]) -> list[str]:
    """텍스트에서 vocab(word_lifecycle의 word 집합)에 실존하는 단어만 순서 보존 + 중복 제거해 반환."""
    if not text or not text.strip():
        return []

    text = text.strip()
    matched: list[str] = []
    seen: set[str] = set()

    kiwi = _get_kiwi()
    if kiwi is not None:
        for noun in _extract_nouns_kiwi(text):
            if noun in vocab and noun not in seen:
                matched.append(noun)
                seen.add(noun)
    else:
        # 간이 매칭: 사전에 있는 단어가 텍스트에 부분 문자열로 등장하는지 확인.
        # 긴 단어부터 검사해 짧은 단어가 긴 단어의 일부로 잘못 매칭되는 것을 줄인다.
        for word in sorted(vocab, key=len, reverse=True):
            if word in text and word not in seen:
                matched.append(word)
                seen.add(word)

    return matched

# 말뭉치 정찰 결과 (2026-07-14)

## 커버리지
- 2004~2008: 연 1만여 문장 → **제외** (다른 연도의 0.3%, 노이즈)
- 2009~2018: 연 350~400만 문장 (CSV, 초기 말뭉치)
- 2019~2022: 연 535~900만 문장 (CSV, 연도별 말뭉치)
- 2023~2024: JSON에 있음
- **분석 범위: 2009~2024 (16년)**
- CSV 총 28.54GB / JSON 44개

## 중요 발견
1. **파일명 연도 ≠ 기사 연도**
   - `NIKL_NEWSPAPER_2020` → 2019년 기사
   - JSON `metadata.year=2024` → 실제 date는 2023
   - → 문서의 `date` 필드만 신뢰할 것

2. **JSON도 전부 신문 말뭉치**
   - `category: '신문 > 인터넷 기반 신문'`
   - 접두사 NIRW/NLRW/NPRW/NWRW/NZRW = 매체 유형
   - → 전부 사용 가능

3. **JSON 구조**
   - `document[i].metadata.date` → 날짜
   - `document[i].paragraph[j].form` → 본문
   - ⚠️ 본문에 `<p>` 태그 붙어있음 → 제거 필요

## CSV 구조
`file_id, doc_id, title, author, publisher, date, topic, original_topic, sentence_id, sentence`
- 한 행 = 한 문장
- 필요한 건 `date`, `sentence` 둘뿐
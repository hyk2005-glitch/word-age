import pandas as pd

life = pd.read_csv("data/processed/word_lifecycle.csv")

print("=== 타입/구조 ===")
print(life.dtypes)
print(life.head())
print(f"단어 수: {len(life)}")
print(f"death_year null: {life['death_year'].isna().sum()}개")

print("\n=== ① 빈도 상위 30 (불용어 점령 여부) ===")
print(life.nlargest(30, "total_freq")[["word", "peak_year", "sharpness"]])

print("\n=== ② sharpness 상위 30 (시대 특정 단어) ===")
print(life.nlargest(30, "sharpness")[["word", "peak_year", "peak_value"]])

print("\n=== ③ 상식 검증 ===")
for w in ["삐삐", "싸이월드", "스마트폰", "코로나", "인공지능", "메타버스"]:
    r = life[life.word == w]
    print(w, r[["birth_year", "peak_year", "death_year", "sharpness"]].to_dict("records"))

print("\n=== ④ 정점 연도 분포 (정규화 검증) ===")
print(life["peak_year"].value_counts().sort_index())
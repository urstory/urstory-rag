# 공개 테스트 데이터셋

외부 기여자가 clone 후 바로 RAG 품질 테스트를 실행할 수 있도록 만든 **저작권 없는 한국어 테스트 데이터셋**입니다.

## 원본 문서

### 마크다운 문서 (자체 작성, CC0 1.0)

| 파일 | 주제 | Q&A 수 | 출처 |
|------|------|--------|------|
| `01_hangul_creation.md` | 한글의 창제와 구조 | 7개 | 공개 사실 (위키백과 수준) |
| `02_korean_geography.md` | 대한민국의 자연지리 | 6개 | 공개 사실 (정부 통계) |
| `03_korean_unesco_heritage.md` | 한국의 유네스코 세계유산 | 7개 | 공개 사실 (유네스코 등재 정보) |
| `04_korean_fermented_food.md` | 한국 전통 발효 식품 | 7개 | 공개 사실 (식품 과학) |
| `05_korean_space_program.md` | 대한민국의 우주 개발 | 8개 | 공개 사실 (KARI/KASA 발표) |

### PDF 문서 (공공기관 발행, 공공누리 제1유형)

| 파일 | 주제 | Q&A 수 | 발행 기관 |
|------|------|--------|----------|
| `bok_economic_terms_700.pdf` | 경제금융용어 700선 | 3개 | 한국은행 (2023) |
| `bok_easy_economics.pdf` | 알기 쉬운 경제이야기 | 3개 | 한국은행 (2025) |
| `kma_climate_change_2020_summary.pdf` | 기후변화 평가보고서 2020 요약 | 3개 | 기상청 (2020) |
| `kma_climate_2025_ch4.pdf` | 기후위기 평가보고서 2025 제4장 | 3개 | 기상청 (2025) |
| `kostat_social_indicators_2024.pdf` | 2024 한국의 사회지표 | 3개 | 통계청 (2025) |

- **총 68개 Q&A 쌍** (마크다운 35개 + 변별력 13개 + PDF 15개 + PDF 변별력 5개)
- 마크다운: 공개적으로 알려진 사실에 기반하여 직접 작성 (CC0 1.0)
- PDF: 공공기관 발행 자료 (공공누리 제1유형, 출처 표시)
- 라이선스 상세: `LICENSE.md` 참조

## Q&A 유형 분류

| 유형 | 예시 | 문항 수 |
|------|------|---------|
| 단순 사실 확인 | "한글날은 언제인가요?" | 14개 |
| 숫자/수치 확인 | "한글로 표현할 수 있는 음절의 총 수는?" | 9개 |
| 다중 정보 종합 | "가장 높은 산 3개의 이름과 높이를 순서대로" | 7개 |
| 비교/분석 | "고추장, 된장, 간장의 염도를 비교하면?" | 5개 |
| PDF 사실 확인 | "2024년 총인구와 합계출산율은?" | 9개 |
| PDF 개념/정의 | "가계부실위험지수(HDRI)란?" | 6개 |
| **다중 문서 추론** | "기후변화 2020과 2025 보고서의 강수량 공통점?" | **6개** |
| **부정 테스트** | "국방 예산 총액과 GDP 대비 비율?" (문서에 없음) | **3개** |
| **유사 혼동** | "1인가구 비율과 고령인구 비율 구분" | **4개** |
| **추론/계산** | "생산가능인구 비율 차이는 몇 %p?" | **5개** |

## 사용 방법

### 1. 문서 인덱싱

공개 데이터셋 문서를 RAG 시스템에 업로드합니다:

```bash
# 백엔드 서버가 실행 중이어야 합니다
# test_files/public_dataset/ 내 .md 및 .pdf 파일을 관리자 UI 또는 API로 업로드
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@test_files/public_dataset/01_hangul_creation.md"
# ... 나머지 마크다운 4개 + PDF 5개 파일도 동일하게 업로드
```

### 2. 품질 테스트 실행

```bash
# 공개 데이터셋만 테스트 (외부 기여자 권장)
python test_files/run_quality_test.py --public-only

# 전체 테스트 (내부 문서 포함, 모든 세트 실행)
python test_files/run_quality_test.py
```

### 3. 결과 확인

- 콘솔에 LLM Judge 점수 + 키워드 재현율 요약 출력
- 상세 결과: `test_files/quality_test_results_public.json`

## Q&A 파일 포맷

참조용 Q&A 파일: `test_files/q_a_public.txt`

```
**Q1. 질문 내용?**
A: 정답 내용.
참조 문서: 01_hangul_creation.md
```

테스트 스크립트 내부에서는 Python 튜플로 관리:

```python
QA_PAIRS = [
    ("질문", "정답"),
    ...
]
```

## 기여 가이드

새로운 Q&A를 추가하려면:

1. `test_files/public_dataset/`에 공개 사실 기반 마크다운 문서 추가
2. `test_files/q_a_public.txt`에 Q&A 쌍 추가
3. `test_files/run_quality_test.py`의 `QA_PAIRS`에 튜플 추가
4. 참조 문서명을 Q&A에 명시

**주의**: 저작권이 있는 콘텐츠를 포함하지 마세요. 위키백과, 공공데이터, Creative Commons 라이선스 자료만 사용합니다.

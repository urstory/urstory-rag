"""RAG 품질 테스트 스크립트 — Q&A에 대해 검색+답변을 실행하고 결과를 평가.

평가 방식:
  1. LLM-as-Judge (GPT-4o) — 메인 지표. 의미적 정확도를 0~100점으로 판정.
  2. 키워드 재현율 — 보조 지표. 숫자/고유명사 exact match.

사용법:
  python test_files/run_quality_test.py
"""
import json
import os
import re
import sys
import time
import httpx

API_URL = "http://localhost:8000"

# .env 파일에서 OPENAI_API_KEY 로드 (환경변수 우선)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("OPENAI_API_KEY="):
                    OPENAI_API_KEY = line.strip().split("=", 1)[1]
                    break

# ---------------------------------------------------------------------------
# LLM-as-Judge (GPT-4o)
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = """당신은 RAG(검색 증강 생성) 시스템의 답변 품질을 평가하는 전문 심사관입니다.

사용자의 질문, 정답(ground truth), RAG 시스템의 답변을 비교하여 0~100점으로 평가하세요.

## 평가 기준

1. **사실 정확성 (40점)**: 핵심 사실이 정답과 일치하는가?
   - 숫자, 금액, 기간, 비율이 정확한가?
   - 고유명사, 전문 용어가 올바른가?
   - 동의어나 명칭 변경(예: 공인인증서↔공동인증서)은 정확한 것으로 인정

2. **완전성 (30점)**: 정답의 핵심 정보를 빠짐없이 포함하는가?
   - 목록 항목이 모두 나열되었는가?
   - 중요한 조건/제한 사항이 포함되었는가?

3. **관련성 (20점)**: 질문에 대해 직접적으로 답변하는가?
   - 불필요한 정보 없이 핵심을 전달하는가?

4. **무해성 (10점)**: 잘못된 정보를 포함하지 않는가?
   - 정답에 없는 거짓 정보를 생성하지 않았는가?

## 응답 형식

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트를 추가하지 마세요.

{"score": <0~100 정수>, "reason": "<한국어로 1~2문장 판정 이유>"}"""

JUDGE_USER_PROMPT = """질문: {question}

정답: {ground_truth}

RAG 답변: {answer}"""


def judge_with_llm(client: httpx.Client, question: str, ground_truth: str, answer: str) -> dict:
    """GPT-4o로 답변 품질을 의미적으로 판정한다.

    Returns:
        {"score": int, "reason": str} 또는 에러 시 {"score": -1, "reason": "..."}
    """
    if not OPENAI_API_KEY:
        return {"score": -1, "reason": "OPENAI_API_KEY 미설정"}

    prompt = JUDGE_USER_PROMPT.format(
        question=question, ground_truth=ground_truth, answer=answer,
    )

    try:
        resp = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o",
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        # JSON 파싱 (```json ... ``` 래핑 대응)
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(content)
    except Exception as e:
        return {"score": -1, "reason": f"Judge 호출 실패: {e}"}

# === 공개 테스트 데이터셋 (저작권 없는 한국어 공개 지식) ===
# 출처: test_files/public_dataset/ 내 5개 문서 (공개 사실 기반)
QA_PAIRS = [
    # 한글의 창제와 구조
    ("훈민정음 해례본은 유네스코 세계기록유산에 언제 등재되었나요?",
     "훈민정음 해례본은 1997년 10월 유네스코 세계기록유산으로 등재되었습니다."),
    ("한글의 기본 글자는 자음과 모음 각각 몇 자로 구성되나요?",
     "한글은 자음 14자와 모음 10자, 총 24자의 기본 글자로 구성됩니다."),
    ("한글 자음 'ㅁ'은 어떤 발음 기관의 모양을 본떠 만들었나요?",
     "ㅁ은 입의 모양을 본떠 만들었으며, 순음(입술소리)에 해당합니다."),
    ("한글 모음의 세 가지 기본 요소는 각각 무엇을 상징하나요?",
     "ㆍ(아래아)는 하늘(天), ㅡ는 땅(地), ㅣ는 사람(人)을 상징하며, 이는 천지인 삼재를 나타냅니다."),
    ("한글로 표현할 수 있는 음절의 총 수는 몇 개이며 어떻게 계산되나요?",
     "총 11,172개이며, 초성 19자, 중성 21자, 종성 28자(종성 없음 포함)의 조합으로 계산됩니다(19 x 21 x 28 = 11,172)."),
    ("한글날은 언제이며, 공휴일에서 제외되었다가 다시 지정된 것은 몇 년인가요?",
     "한글날은 매년 10월 9일이며, 1970년에 공휴일에서 제외되었다가 2013년부터 다시 공휴일로 지정되었습니다."),
    ("한글이 자질 문자로 분류되는 이유는 무엇인가요?",
     "글자의 형태가 해당 소리의 음성학적 자질을 반영하기 때문입니다. 예를 들어 ㄱ에서 획을 더하면 ㅋ이 되는 가획의 원리는 소리가 세지는 것을 시각적으로 표현한 것입니다."),
    # 대한민국의 자연지리
    ("대한민국 해안선의 총 길이는 얼마이며, 섬 해안선이 차지하는 비율은 몇 %인가요?",
     "해안선의 총 길이는 약 12,729km이며, 섬 해안선이 약 8,653km로 전체의 약 68%를 차지합니다."),
    ("대한민국에서 가장 높은 산 3개의 이름과 해발 높이를 순서대로 말해주세요.",
     "한라산(1,947m), 지리산(1,915m), 설악산(1,708m) 순입니다."),
    ("낙동강의 유역 면적은 얼마이며, 대한민국 4대 강 중 유역 면적 순위는 어떻게 되나요?",
     "낙동강의 유역 면적은 23,384km²로, 대한민국 4대 강 중 가장 넓습니다."),
    ("한강은 어디에서 발원하며 유역 면적은 대한민국 전체 면적의 약 몇 %를 차지하나요?",
     "한강은 강원도 태백시 금대봉 부근의 검룡소에서 발원하며, 유역 면적 약 26,018km²로 대한민국 전체 면적의 약 26%를 차지합니다."),
    ("대한민국의 연평균 강수량은 얼마이며, 강수량이 집중되는 시기는 언제인가요?",
     "연평균 강수량은 약 1,300mm이며, 강수량의 약 50~60%가 6월부터 9월 사이의 장마철과 태풍 시기에 집중됩니다."),
    ("대한민국에서 가장 큰 섬 3개의 이름과 면적을 순서대로 말해주세요.",
     "제주도(1,849km²), 거제도(379km²), 진도(363km²) 순입니다."),
    # 한국의 유네스코 세계유산
    ("대한민국이 보유한 유네스코 세계유산은 총 몇 건이며, 문화유산과 자연유산은 각각 몇 건인가요?",
     "2024년 기준 총 16건으로, 문화유산 14건, 자연유산 2건입니다."),
    ("해인사 장경판전에 보관된 고려대장경 경판의 총 수는 몇 장이며, 제작 기간은 얼마인가요?",
     "고려대장경 경판은 총 81,258장이며, 1237년부터 1248년까지 약 16년에 걸쳐 제작되었습니다."),
    ("수원 화성은 어떤 왕이 누구의 묘를 이전하면서 건설하였으며, 축성 기간은 얼마인가요?",
     "정조대왕이 아버지 사도세자의 묘를 수원으로 이전하면서 건설하였으며, 1794년부터 1796년까지 약 2년 8개월에 걸쳐 축성되었습니다."),
    ("종묘 정전의 규모와 모셔진 왕과 왕비 신위의 수는 각각 얼마인가요?",
     "정전은 정면 19칸, 측면 4칸의 단일 목조 건물이며, 총 49위의 왕과 왕비의 신위가 모셔져 있습니다."),
    ("제주도 만장굴의 총 길이는 얼마이며, 거문오름 용암동굴계에 포함된 동굴은 무엇인가요?",
     "만장굴의 총 길이는 약 7,416m이며, 거문오름 용암동굴계에는 만장굴, 김녕굴, 벵뒤굴, 당처물동굴, 용천동굴이 포함됩니다."),
    ("조선 왕릉 세계유산에서 제외된 2기의 왕릉은 어디에 위치하며 어떤 왕릉인가요?",
     "북한 개성에 위치한 제릉(태조의 첫 번째 왕비 신의왕후릉)과 후릉(정종과 정안왕후릉) 2기가 등재에서 제외되었습니다."),
    ("한국의 갯벌 유네스코 자연유산에 포함된 4개 지역은 어디인가요?",
     "서천, 고창, 신안, 보성-순천 4개 지역의 갯벌이 2021년에 자연유산으로 등재되었습니다."),
    # 한국 전통 발효 식품
    ("김치 발효 과정에서 주요 역할을 하는 두 가지 유산균은 무엇이며, 발효 단계별 우세 균은 어떻게 달라지나요?",
     "류코노스톡 메센테로이데스(Leuconostoc mesenteroides)와 락토바실러스 플란타룸(Lactobacillus plantarum)이며, 발효 초기에는 류코노스톡이, 후기에는 락토바실러스가 우세합니다."),
    ("김치의 최적 발효 온도와 숙성 기간은 어떻게 되나요?",
     "최적 발효 온도는 0~5°C이며, 이 온도에서 약 2~3주간 숙성하면 맛과 영양이 최고점에 달합니다."),
    ("전통 된장 제조 시 메주를 담그는 소금물의 염도는 약 몇 %이며, 발효 기간은 얼마인가요?",
     "메주를 소금물(염도 약 18~22%)에 담가 약 40~60일간 발효시킵니다."),
    ("된장 숙성 과정에서 감칠맛을 생성하는 주요 미생물은 무엇이며, 어떤 작용을 하나요?",
     "바실러스 서브틸리스(Bacillus subtilis)가 단백질을 아미노산으로 분해하여 감칠맛을 생성합니다."),
    ("고추장, 된장, 간장의 평균 염도를 각각 비교하면 어떻게 되나요?",
     "고추장은 약 8~12%, 된장은 약 12~14%, 간장은 약 22~25%로, 고추장이 가장 낮고 간장이 가장 높습니다."),
    ("막걸리의 발효 과정에서 전분을 포도당으로 분해하는 미생물과 포도당을 알코올로 전환하는 미생물은 각각 무엇인가요?",
     "아스페르길루스 오리제(Aspergillus oryzae)가 전분을 포도당으로 분해하고, 사카로마이세스 세레비시에(Saccharomyces cerevisiae)가 포도당을 알코올로 전환합니다."),
    ("고추장이 문헌에 최초로 기록된 것은 어떤 책이며, 언제 작성되었나요?",
     "고추장이 문헌에 최초로 기록된 것은 1765년 유중림의 증보산림경제입니다."),
    # 대한민국의 우주 개발
    ("대한민국이 누리호 발사에 성공하며 자국 기술로 실용급 위성을 궤도에 올린 세계 몇 번째 국가가 되었나요?",
     "2022년 누리호 발사에 성공하며 자국 기술로 실용급 위성을 궤도에 올린 세계 7번째 국가가 되었습니다."),
    ("누리호 1단 로켓의 엔진 구성과 총 추력은 어떻게 되나요?",
     "1단 로켓에는 75톤급 액체 엔진 4기가 클러스터링되어 총 300톤의 추력을 발생시킵니다."),
    ("나로호 3차 발사의 날짜와 결과는 어떻게 되나요?",
     "2013년 1월 30일 3차 발사에서 나로과학위성(100kg)을 고도 300~1,500km 타원 궤도에 성공적으로 투입하였습니다."),
    ("다누리 탐사선이 달 궤도에 진입하기까지 어떤 궤도를 이용했으며 비행 기간은 얼마인가요?",
     "연료 절약을 위해 탄도형 달 전이궤도(BLT)를 이용하여 약 4.5개월간 비행한 후, 2022년 12월 27일 달 궤도에 진입하였습니다."),
    ("한국형 위성항법시스템(KPS)의 위성 구성과 완성 목표 연도는 어떻게 되나요?",
     "정지궤도 3기, 경사궤도 5기 총 8기의 위성으로 구성될 예정이며, 2035년 완성을 목표로 하고 있습니다."),
    ("KPS의 보정 서비스 적용 시 위치 정밀도 목표는 얼마이며, 기존 GPS와 비교하면 어떤가요?",
     "보정 서비스 적용 시 10cm 이내의 정밀도를 목표로 하며, 이는 기존 GPS의 민간용 정밀도(약 3~5m)보다 크게 향상된 수준입니다."),
    ("다누리에 탑재된 NASA 제공 카메라의 이름과 용도는 무엇인가요?",
     "섀도캠(ShadowCam)이라는 초고감도 카메라로, 달 극지방의 영구 음영 지역을 촬영하는 데 사용됩니다."),
    ("누리호의 총 길이, 총 중량, 위성 투입 능력은 각각 얼마인가요?",
     "총 길이 47.2m, 총 중량 약 200톤이며, 1.5톤급 위성을 지구 저궤도(600~800km)에 투입할 수 있습니다."),

    # === 변별력 강화 Q&A (다중 문서 추론 / 부정 테스트 / 유사 혼동 / 추론) ===

    # [다중 문서 추론] — 2개 이상 문서 정보를 종합해야 답변 가능
    ("제주도는 대한민국에서 가장 큰 섬인데, 제주도와 관련된 유네스코 세계유산에는 어떤 것들이 있으며 각각의 주요 특징은 무엇인가요?",
     "제주도와 관련된 유네스코 세계유산은 '제주 화산섬과 용암 동굴(2007년)'로, 한라산 천연보호구역, 거문오름 용암동굴계, 성산일출봉 3개 구역이 포함됩니다. 거문오름 용암동굴계에는 만장굴(총 길이 약 7,416m), 김녕굴, 벵뒤굴, 당처물동굴, 용천동굴이 포함되며, 제주도의 면적은 1,849km²입니다."),
    ("1997년에 유네스코에 등재된 한국 관련 유산 2건의 이름과 각각의 의의를 설명해주세요.",
     "1997년에는 훈민정음 해례본이 유네스코 세계기록유산으로 등재되었고, 수원 화성이 유네스코 세계유산(문화유산)으로 등재되었습니다. 훈민정음 해례본은 한글의 창제 원리를 설명한 책이며, 수원 화성은 정조대왕이 건설한 조선 후기 성곽입니다."),
    ("대한민국의 전통 발효 식품 중 유네스코에 등재된 것은 무엇이며, 등재 연도와 범주는 어떻게 되나요?",
     "김장 문화가 2013년 12월 유네스코 인류무형문화유산으로 등재되었습니다. 김장은 김치를 담그는 전통 문화로, 김치는 한국 전통 발효 식품의 대표 주자입니다."),
    ("한강의 길이와 낙동강의 길이를 비교하고, 유역 면적이 더 넓은 강은 어느 쪽이며 그 차이는 얼마인가요?",
     "한강은 총 길이 514km, 낙동강은 510km로 한강이 약간 더 깁니다. 그러나 유역 면적은 한강이 약 26,018km², 낙동강이 23,384km²로 한강이 약 2,634km² 더 넓습니다."),

    # [부정 테스트] — 문서에 없는 내용을 질문 (RAG가 "정보 없음"으로 답해야 함)
    ("대한민국의 원자력 발전소는 총 몇 기이며, 가장 최근에 가동을 시작한 원전은 어디인가요?",
     "제공된 문서에는 대한민국의 원자력 발전소에 대한 정보가 포함되어 있지 않습니다."),
    ("한국의 반도체 산업 규모와 세계 시장 점유율은 어떻게 되나요?",
     "제공된 문서에는 한국의 반도체 산업에 대한 정보가 포함되어 있지 않습니다."),
    ("대한민국의 국방 예산 총액과 GDP 대비 비율은 얼마인가요?",
     "제공된 문서에는 대한민국의 국방 예산에 대한 정보가 포함되어 있지 않습니다."),

    # [유사 혼동] — 비슷한 수치/사실을 정확히 구분해야 하는 질문
    ("나로호와 누리호는 각각 세계 몇 번째 기록을 세웠으며, 그 기록의 차이점은 무엇인가요?",
     "나로호는 2013년 발사 성공으로 세계 11번째로 자국 발사장에서 위성을 궤도에 올린 국가 기록을 세웠습니다(1단은 러시아 제작). 누리호는 2022년 발사 성공으로 자국 기술로 실용급 위성을 궤도에 올린 세계 7번째 국가 기록을 세웠습니다(전체 독자 개발)."),
    ("대한민국 4대 강의 길이를 긴 순서대로 나열하고, 유역 면적이 가장 넓은 강과 가장 긴 강이 다른지 확인해주세요.",
     "길이 순: 한강(514km), 낙동강(510km), 금강(401km), 영산강(136km). 가장 긴 강은 한강이지만 유역 면적이 가장 넓은 강은 낙동강(23,384km²)이 아니라 한강(약 26,018km²)입니다. 즉 가장 긴 강과 유역 면적이 가장 넓은 강 모두 한강입니다."),
    ("된장과 고추장의 발효 기간을 각각 비교하고, 어느 쪽의 숙성 기간이 더 긴가요?",
     "된장은 메주를 소금물에 담가 약 40~60일간 발효 후 분리하여 다시 숙성시킵니다. 고추장의 숙성 기간은 보통 3~6개월입니다. 고추장의 전체 숙성 기간이 된장의 초기 발효 기간보다 길지만, 된장도 분리 후 추가 숙성이 필요하므로 전체적으로는 비슷하거나 된장이 더 길 수 있습니다."),

    # [추론] — 직접 기술되지 않고 유추가 필요한 질문
    ("누리호 2단과 3단 엔진의 추력 차이는 몇 배인가요?",
     "2단에는 75톤급 엔진 1기(추력 75톤), 3단에는 7톤급 엔진 1기(추력 7톤)가 장착되어 있으므로, 2단 엔진의 추력이 3단의 약 10.7배입니다."),
    ("대한민국의 유인도 비율은 전체 섬 중 약 몇 %인가요?",
     "전체 약 3,348개 섬 중 유인도가 약 472개이므로, 유인도 비율은 약 14.1%입니다."),
    ("고려대장경 제작에 1년당 평균 약 몇 장의 경판을 만든 셈인가요?",
     "총 81,258장을 약 16년(1237~1248년, 실제 12년이지만 문서 기준 약 16년)에 걸쳐 제작했으므로, 연평균 약 5,079장입니다."),

    # === PDF 문서 기반 Q&A (공공기관 발행 공공누리 제1유형) ===

    # 2024 한국의 사회지표 (통계청)
    ("2024년 대한민국의 총인구와 합계출산율은 각각 얼마인가요?",
     "2024년 총인구는 5,175만 명이며, 합계출산율은 0.75명입니다. 출생아 수는 23만 8천 3백 명으로 2015년 이후 처음으로 전년대비 증가하였습니다."),
    ("2072년 대한민국의 인구 전망에서 총인구와 65세 이상 고령인구 비율은 어떻게 예측되나요?",
     "2072년에는 총인구가 3,622만 명으로 감소하고, 65세 이상 고령인구가 1,727만 명으로 전체의 47.7%가 될 것으로 전망됩니다."),
    ("2023년 대한민국의 기대수명은 몇 년이며, 사망원인 1위는 무엇인가요?",
     "2023년 기대수명은 83.5년(남자 80.6년, 여자 86.4년)이며 OECD 회원국 중 5위입니다. 사망원인 1위는 악성신생물(암)로 인구 10만 명당 166.7명이 사망하였습니다."),

    # 경제금융용어 700선 (한국은행)
    ("가계부실위험지수(HDRI)란 무엇이며, 위험가구로 분류되는 기준은 무엇인가요?",
     "가계부실위험지수(HDRI)는 가구의 소득 흐름과 금융·실물 자산을 종합적으로 고려하여 가계부채의 부실위험을 평가하는 지표입니다. DSR(원리금상환비율) 40%, DTA(부채/자산비율) 100%일 때 100의 값을 갖도록 설정되며, 지수가 100을 초과하는 가구를 '위험가구'로 분류합니다."),
    ("가계수지란 무엇이며, 통계청에서 어떻게 조사하나요?",
     "가계수지란 가정에서 일정 기간의 수입(명목소득)과 지출을 비교해서 남았는지 모자랐는지를 표시한 것입니다. 통계청에서 선정된 가계에 가계부를 나누어 주고 한 달간의 소득과 지출을 기록하도록 한 다음 이를 토대로 통계를 작성합니다."),
    ("가계순저축률이란 무엇이며, 왜 중요한 지표인가요?",
     "가계순저축률은 가계부문의 순저축액을 가계순처분가능소득과 사회적 현물이전 금액, 연금기금의 가계순지분 증감조정액을 합계한 금액으로 나눈 비율입니다. 가계부문의 저축성향을 가장 잘 나타내주는 지표입니다."),

    # 알기 쉬운 경제이야기 (한국은행)
    ("혼합경제란 무엇이며, 왜 대부분의 나라가 혼합경제를 채택하고 있나요?",
     "혼합경제란 시장경제체제에 정부가 일정부분 개입하는 경제제도입니다. 시장경제가 소득분배의 차이를 줄이지 못하고 경기변동과 실업, 공공재 부족 등의 단점이 있어 이를 완화하기 위해 정부의 시장개입이 필요하므로 대부분의 나라가 혼합경제를 채택하고 있습니다."),
    ("아담 스미스가 말한 '보이지 않는 손'이란 무엇인가요?",
     "영국의 경제학자 아담 스미스는 시장에서 형성되는 가격이 무엇을 생산하고 어떻게 생산하며 어떻게 나누어야 할 것인지의 경제문제를 해결하는 시장의 역할을 '보이지 않는 손'에 비유했습니다. 가격기구의 효율적인 자원배분 기능은 시장참가자의 경쟁을 통하여 이루어집니다."),
    ("경제학에서 미시경제와 거시경제를 각각 무엇에 비유하나요?",
     "미시경제는 개별 경제주체(가계, 기업)의 의사결정을 분석하는 분야로 나무 하나하나의 특성을 파악하는 것에, 거시경제는 국민소득·물가·고용·이자율·환율 등 경제 전체를 분석하는 분야로 숲 전체의 모양과 특성을 파악하는 것에 비유합니다."),

    # 한국 기후변화 평가보고서 2020 (기상청)
    ("1912~2017년 동안 한반도의 여름철 강수량 변화 추세는 어떠하나요?",
     "한반도의 강수량 증가 경향은 여름철에 뚜렷했으며, 1912~2017년 동안 여름철 강수량은 10년당 +11.6mm 증가하였습니다. 반면 가을과 봄, 겨울철은 그 변화 경향이 뚜렷하지 않았습니다."),
    ("1992~2018년간 남극 빙산 질량 소실 규모와 그로 인한 해수면 상승은 어느 정도인가요?",
     "남극 빙산 질량은 1992~2018년간 약 3조 톤이 소실되었으며, 이는 7.6mm의 전 지구 해수면 상승을 유발한 것으로 추정됩니다. 총 증가분의 약 40%가 최근 5년 사이 급격히 발생하였습니다."),
    ("북극 해빙 면적의 6월 감소 추세는 어떠하나요?",
     "북극 해빙 면적은 6월 기준 매 10년마다 -4.1±0.5%씩 감소하는 추세입니다."),

    # 한국 기후위기 평가보고서 2025 제4장 (기상청)
    ("한국 기후위기 평가보고서 2025가 다루는 부문은 무엇인가요?",
     "수자원, 생태계, 산림, 농업, 해양 및 수산, 산업 및 에너지, 보건, 인간정주공간과 복지, 적응 및 취약성 등 9개 부문을 다루고 있으며, 총 10장으로 구성되어 있습니다."),
    ("기후위기 평가보고서 2025에 따르면 제주와 경북의 연평균 강수량 차이는 얼마인가요?",
     "제주 권역의 연평균 강수량은 1,820.7mm로 상위권인 반면, 경북 권역은 1,154.1mm로 하위권에 머물렀습니다. 그 차이는 약 667mm에 달합니다."),
    ("안면도 지구대기감시소에서 측정한 이산화탄소 농도와 증가 속도는 어떠한가요?",
     "안면도 지구대기감시소에서 측정한 이산화탄소 배경농도가 430ppm을 넘어섰으며, 매년 약 3ppm씩 증가하고 있습니다. 산업화 이전 대비 전 지구평균기온 2°C 상승을 의미하는 450ppm까지 6~7년밖에 남지 않은 상황입니다."),

    # === PDF 변별력 강화 Q&A ===

    # [다중 문서 추론] — PDF 간, PDF+마크다운 간 종합
    ("2020년 기후변화 보고서와 2025년 기후위기 보고서 모두에서 확인되는 한반도 강수량의 공통적 특성은 무엇인가요?",
     "두 보고서 모두 한반도 강수량의 증가와 지역별 격차 심화를 공통적으로 보고합니다. 2020년 보고서에서는 1912~2017년 동안 여름철 강수량이 10년당 +11.6mm 증가했다고 밝혔고, 2025년 보고서에서는 제주(1,820.7mm)와 경북(1,154.1mm)의 연평균 강수량 격차가 뚜렷하다고 분석하였습니다."),
    ("2024년 대한민국의 수도권 인구 비율과 국토의 연평균 강수량은 각각 얼마인가요?",
     "수도권(서울·경기·인천) 인구는 2,630만 명으로 전체 인구(5,175만 명)의 50.8%를 차지하며(사회지표), 대한민국의 연평균 강수량은 약 1,300mm입니다(자연지리 문서)."),

    # [유사 혼동] — PDF 내 비슷한 비율 구분
    ("2023년 기준 대한민국의 1인가구 비율과 65세 이상 고령인구 비율을 각각 구분하여 말해주세요.",
     "2023년 기준 1인가구 비율은 전체 가구의 35.5%이고, 2024년 기준 65세 이상 고령인구 비율은 전체 인구의 19.2%입니다. 1인가구는 가구 구성 기준이고, 고령인구는 연령 기준이므로 서로 다른 지표입니다."),

    # [추론] — 직접 기술되지 않고 계산/유추 필요
    ("2024년과 2072년 대한민국의 생산가능인구(15~64세) 비율 차이는 몇 %p인가요?",
     "2024년 생산가능인구(15~64세)는 3,633만 명(70.2%), 2072년에는 1,658만 명(45.8%)으로 전망되므로, 그 차이는 약 24.4%p입니다."),
    ("안면도 CO2 농도가 현재 430ppm이고 매년 3ppm씩 증가한다면, 450ppm에 도달하는 데 약 몇 년이 걸리나요?",
     "(450-430)/3 ≈ 약 6~7년이 소요됩니다. 보고서에서도 450ppm까지 6~7년밖에 남지 않았다고 밝히고 있습니다."),
]


def extract_keywords(text: str) -> set[str]:
    """핵심 키워드 추출 (숫자, 고유명사 위주)."""
    keywords = set()
    # 숫자+단위 패턴
    for m in re.findall(r'\d+[%만원명회개월일시간건년]?', text):
        keywords.add(m)
    # 영문 키워드 (기술 용어)
    for m in re.findall(r'[A-Za-z][A-Za-z0-9_.]+', text):
        if len(m) >= 3 and m.lower() not in ('the', 'and', 'for', 'that', 'this'):
            keywords.add(m)
    # 주요 한글 단어 (3글자 이상)
    for word in re.findall(r'[가-힣]{3,}', text):
        if word not in ('있습니다', '합니다', '됩니다', '입니다', '가능합니다', '경우에는',
                       '대해서', '이상이', '이상을', '이상인', '이상이어야', '포함하여',
                       '수준입니다', '것입니다', '않습니다', '없습니다', '그리고'):
            keywords.add(word)
    return keywords


def check_answer_quality(question: str, ground_truth: str, answer: str) -> dict:
    """답변 품질을 키워드 매칭 기반으로 평가."""
    gt_keywords = extract_keywords(ground_truth)
    ans_keywords = extract_keywords(answer)

    if not gt_keywords:
        return {"keyword_recall": 0.0, "matched": set(), "missed": set()}

    matched = gt_keywords & ans_keywords
    missed = gt_keywords - ans_keywords
    recall = len(matched) / len(gt_keywords)

    return {
        "keyword_recall": recall,
        "matched": matched,
        "missed": missed,
        "gt_keywords": gt_keywords,
    }


def call_with_retry(client, question, max_retries=3, base_delay=3.0):
    """503/429 에러 시 지수 백오프로 재시도."""
    for attempt in range(max_retries + 1):
        try:
            resp = client.post(
                f"{API_URL}/api/search",
                json={"query": question, "generate_answer": True},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (503, 429, 502) and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"  {e.response.status_code} 에러, {delay:.0f}초 후 재시도 ({attempt+1}/{max_retries})...")
                time.sleep(delay)
            else:
                raise
        except httpx.ReadTimeout:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"  타임아웃, {delay:.0f}초 후 재시도 ({attempt+1}/{max_retries})...")
                time.sleep(delay)
            else:
                raise


REQUEST_DELAY = 0.5


def get_auth_headers() -> dict:
    """API 인증 토큰을 획득한다."""
    login_client = httpx.Client(timeout=10.0)
    # 환경변수 또는 기본 관리자 계정
    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "ChangeMe1234!@#$")
    try:
        resp = login_client.post(
            f"{API_URL}/api/auth/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        print(f"  인증 실패 (공개 API로 시도): {e}")
        return {}


def main():
    client = httpx.Client(timeout=120.0)
    judge_client = httpx.Client(timeout=30.0)
    base = os.path.dirname(os.path.abspath(__file__))

    # 인증 토큰 획득
    auth_headers = get_auth_headers()
    if auth_headers:
        print("  인증: Bearer 토큰 획득 완료")
    client.headers.update(auth_headers)

    use_judge = bool(OPENAI_API_KEY)
    if not use_judge:
        print("OPENAI_API_KEY 미설정 -- 키워드 재현율만으로 평가합니다.")
        print()

    n = len(QA_PAIRS)
    results_summary = []

    print("=" * 80)
    print(f"  RAG 품질 테스트 -- 공개 데이터셋 ({n}개 Q&A)")
    if use_judge:
        print("  평가 모드: LLM-as-Judge (GPT-4o) + 키워드 재현율")
    else:
        print("  평가 모드: 키워드 재현율 only")
    print("=" * 80)
    print()

    total_recall = 0.0
    total_judge_score = 0.0
    judge_count = 0
    search_hit_count = 0

    for i, (question, ground_truth) in enumerate(QA_PAIRS, 1):
        print(f"--- Q{i}: {question[:60]}...")

        if i > 1:
            time.sleep(REQUEST_DELAY)

        try:
            start = time.time()
            data = call_with_retry(client, question)
            elapsed = time.time() - start
        except Exception as e:
            print(f"  ERROR: {e}")
            results_summary.append({"q": i, "error": str(e)})
            continue

        answer = data.get("answer", "")
        search_results = data.get("results", [])
        top_score = search_results[0]["score"] if search_results else 0

        # 1) 키워드 재현율 (보조 지표)
        quality = check_answer_quality(question, ground_truth, answer)
        recall = quality["keyword_recall"]
        total_recall += recall

        hit = top_score > 0.3
        if hit:
            search_hit_count += 1

        kw_status = "GOOD" if recall >= 0.5 else "WEAK" if recall >= 0.2 else "MISS"

        # 2) LLM-as-Judge (메인 지표)
        judge_score = -1
        judge_reason = ""
        judge_grade = ""
        if use_judge:
            judge_result = judge_with_llm(judge_client, question, ground_truth, answer)
            judge_score = judge_result.get("score", -1)
            judge_reason = judge_result.get("reason", "")
            if judge_score >= 0:
                total_judge_score += judge_score
                judge_count += 1
                judge_grade = (
                    "GOOD" if judge_score >= 70
                    else "PARTIAL" if judge_score >= 40
                    else "FAIL"
                )

        # 출력
        if use_judge and judge_score >= 0:
            print(f"  Judge: {judge_grade} ({judge_score}점) | KW: {kw_status} (recall={recall:.0%}) | score={top_score:.4f} | {elapsed:.1f}s")
            print(f"  -> {judge_reason}")
        else:
            print(f"  {kw_status} | recall={recall:.0%} | top_score={top_score:.4f} | {elapsed:.1f}s")
            if quality.get("missed"):
                missed_str = ", ".join(list(quality["missed"])[:5])
                print(f"  누락 키워드: {missed_str}")

        result_entry = {
            "q": i,
            "kw_status": kw_status,
            "recall": recall,
            "top_score": top_score,
            "elapsed": elapsed,
        }
        if use_judge:
            result_entry["judge_score"] = judge_score
            result_entry["judge_grade"] = judge_grade
            result_entry["judge_reason"] = judge_reason
        results_summary.append(result_entry)

    # 결과 요약
    kw_good = sum(1 for r in results_summary if r.get("kw_status") == "GOOD")
    kw_weak = sum(1 for r in results_summary if r.get("kw_status") == "WEAK")
    kw_miss = sum(1 for r in results_summary if r.get("kw_status") == "MISS")
    errors = sum(1 for r in results_summary if "error" in r)

    print()
    print("=" * 80)
    print(f"  결과 요약 ({n}개 Q&A)")
    print("=" * 80)

    if use_judge and judge_count > 0:
        j_good = sum(1 for r in results_summary if r.get("judge_grade") == "GOOD")
        j_partial = sum(1 for r in results_summary if r.get("judge_grade") == "PARTIAL")
        j_fail = sum(1 for r in results_summary if r.get("judge_grade") == "FAIL")
        avg_judge = total_judge_score / judge_count

        print(f"  [LLM Judge -- GPT-4o]")
        print(f"  평균 점수:       {avg_judge:.1f}/100")
        print(f"  GOOD (>=70):     {j_good}개 ({j_good/n:.0%})")
        print(f"  PARTIAL (40-69): {j_partial}개 ({j_partial/n:.0%})")
        print(f"  FAIL (<40):      {j_fail}개 ({j_fail/n:.0%})")
        print()

    print(f"  [키워드 재현율]")
    print(f"  총 질문: {n}개")
    print(f"  GOOD (recall >= 50%): {kw_good}개")
    print(f"  WEAK (recall 20-49%): {kw_weak}개")
    print(f"  MISS (recall < 20%):  {kw_miss}개")
    print(f"  ERROR:                {errors}개")
    print(f"  평균 키워드 재현율:   {total_recall / n:.1%}")
    print(f"  검색 적중률 (score>0.3): {search_hit_count}/{n} ({search_hit_count/n:.0%})")
    print()

    results_file = os.path.join(base, "quality_test_results.json")
    with open(results_file, "w") as f:
        json.dump(results_summary, f, indent=2, ensure_ascii=False)
    print(f"  상세 결과 저장: {results_file}")


if __name__ == "__main__":
    main()

"""
txt2sql.py 에서 사용하는 LLM 프롬프트 모음.
동적 변수를 받아 완성된 프롬프트 문자열을 반환하는 함수로 구성.
"""


def prompt_festival_info(info: str) -> str:
    """축제 기본 정보를 자연어로 설명"""
    return f"""다음 축제 정보를 간결하고 명확하게 정리해주세요.

{info}

[작성 규칙]
1. 축제명을 굵게(**축제명**) 표시
2. 기간, 장소, 주최 등을 마크다운 리스트(-)로 정리
3. 축제 설명이 있으면 한 줄로 요약해서 포함 (원문 그대로 붙여넣기 금지)
4. 홈페이지가 있으면 링크 제공
5. 마지막에 "통계 데이터가 필요하시면 축제명을 말씀해 주세요." 한 줄 추가
6. 감성적·과장된 표현 금지, 사실 정보만 전달
7. 간결하게 (5줄 이내)

답변:"""


# ── 프롬프트 섹션 상수 ──────────────────────────────────────────────────────────
# prompt_extract_festival_context() 조립 블록. 각 섹션을 독립적으로 수정 가능.

_EXTRACTION_RULES = """[추출 규칙]
1. region: 지역명 또는 축제명 중 DB 검색에 가장 유용한 키워드를 추출
   - 지역명 예시: "수원", "화성시", "서울"
   - 축제명 예시: "정조대왕 능행차", "화성문화제", "수원화성문화제"
   - 둘 다 있으면 더 구체적인 것(축제명 우선)
   - ⚠️ "수원축제", "서울축제" 처럼 [지역명+축제/행사] 형태는 일상어이며 DB 축제명이 아님
     → 지역명만 추출 (예: "수원축제" → "수원", "서울행사" → "서울")
   - ⚠️ "관내", "인접", "인접 지역", "관외" 는 방문인구 유입지 구분 용어(데이터 차원값)이며 실제 지역명이 아님
     → 이전 대화에 축제가 있으면 region: null, year: null로 반환 (이전 축제 컨텍스트 재사용)
2. 질문에 구체적인 연도가 있으면 year에 추출
   - "올해", "이번 해" → 현재 연도
   - "작년", "지난해" → 현재 연도 - 1
   - "재작년", "2년 전" → 현재 연도 - 2
3. "최근에", "가장 최근", "요즘" 등은 연도를 특정하지 않는 표현 → year: null
4. month: 질문에 월(月) 정보가 있으면 2자리 문자열로 추출
   - "9월", "9월에", "9월달" → month: "09"
   - "10월" → month: "10"
   - "이번 달", "이번 월" → month: 현재 월 2자리 (예: 현재 4월이면 "04")
   - "다음 달", "지난 달" → month: null (연도처럼 특정 불가)
   - 월 정보가 없으면 → month: null
   - ⚠️ month는 year와 독립적: "9월 방문인구" → month: "09", year: null
5. "이 축제", "그 행사", "해당 축제" 등 지시어가 있으면:
   - [직전에 언급된 축제]가 있으면 그 축제명 또는 지역명을 region으로, year는 null로 추출
   - [직전에 언급된 축제]가 없으면 region, year 모두 null
6. 이전 대화에서 이어지는 질문이면 이전 대화의 축제/지역 정보를 활용
7. "해당 날짜", "그 날", "같은 날", "이 날짜", "그 날짜" 등 날짜 지시어가 있으면:
   - 이전 대화(assistant 답변)에서 언급된 가장 최근 날짜(YYYY년 MM월 DD일 또는 YYYYMMDD 형태)를 specific_date로 추출
   - 예: 직전 답변에 "2025년 9월 28일"이 있으면 → specific_date: "20250928"
   - 날짜를 찾을 수 없으면 specific_date: null"""

_INTENT_CRITERIA = """[의도 분류 기준]
- "축제_목록": 축제 개수/갯수, 목록/리스트, 어떤 축제들 요청
  ⚠️ "볼 수 있는 축제 목록", "확인할 수 있는 축제 목록", "조회 가능한 축제 목록", "내 축제 목록", "등록된 축제" 등 접근 가능한 축제 목록 요청도 반드시 "축제_목록"
  ⚠️ "데이터" 단어가 없고 "목록/리스트/개수"가 있으면 → 반드시 "축제_목록" ("내가 확인할 수 있는 축제 목록" ≠ "내가 확인할 수 있는 데이터")
  ⚠️ 목록/리스트의 대상이 "데이터"인 경우는 축제_목록 아님 → 반드시 "데이터_보유_현황"
     예: "데이터 목록", "데이터의 목록", "데이터 리스트", "확인할 수 있는 데이터의 목록" → "데이터_보유_현황"
     구분: "축제 목록" (목록 대상=축제) → 축제_목록 / "데이터 목록" (목록 대상=데이터) → 데이터_보유_현황
- "축제_정보": 특정 축제의 기간/장소/주최/소개 등 기본 정보 요청
  ⚠️ "언제야?", "어디서 해?", "기간 알려줘", "주최가 어디야?", "홈페이지 알려줘" 등 → "축제_정보"
  ⚠️ 이전 컨텍스트 축제에 대해 "이 축제 기간은?" 처럼 지시어만 있어도 → "축제_정보"
  ⚠️ 기본 정보(기간/장소)와 통계(매출/방문인구)를 동시에 요청 시 → "통계_분석" 우선
- "통계_분석": 방문인구/매출/연령대/성별/시간대 등 데이터 분석 요청 (기본값)
  ⚠️ "가장 [지표]이 높은/낮은/많은 [분류]는 어디인가요?" 패턴 → 반드시 "통계_분석" ("어디"=장소 아님, 어느 항목인지 묻는 표현)
  ⚠️ 매출/방문인구/연령대/성별 등 통계 키워드가 포함되면 "어디인가요?", "어느 쪽?" 표현이 있어도 반드시 "통계_분석"
- "일반_질문": 교통편/가는 방법/주변 맛집/날씨/숙박 등 축제 통계 DB와 무관한 외부 정보 요청
  ⚠️ "어떻게 가", "가는 방법", "교통", "주차", "역에서", "맛집", "날씨", "숙박" 등 → 반드시 "일반_질문"
  ⚠️ 단, 매출/방문인구/연령대/성별 등 통계 키워드가 함께 있으면 "일반_질문" 금지 → "통계_분석"
  ⚠️ 단, "유동인구가 있는 축제", "방문인구 데이터가 있는 축제", "매출 데이터 있는 축제" 처럼 데이터 보유 여부를 묻는 질문은 반드시 "데이터_보유_현황"으로 분류 (일반_질문 아님)
- "데이터_보유_현황": 내 계정에서 접근 가능한 축제별 데이터 종류/현황 확인 요청
  ⚠️ 핵심 판별: "어떤/무슨 데이터가 있나?" 처럼 데이터 존재 여부/종류를 묻는 질문
  ⚠️ 트리거 표현: "무슨 데이터", "어떤 데이터", "데이터가 뭐가 있", "확인할 수 있는 데이터", "축제들의 데이터",
     "확인할 수 있는 축제 데이터", "볼 수 있는 데이터", "이용할 수 있는 데이터",
     "보유한 데이터", "어떤 자료", "데이터 종류", "어떤 통계", "데이터가 있어", "데이터 현황",
     "데이터 목록", "데이터의 목록", "데이터 리스트", "확인할 수 있는 데이터의 목록" 등
  ⚠️ "데이터" 단어가 포함 + "뭐가 있", "뭐야", "어떤게 있" 패턴 → 반드시 "데이터_보유_현황"
  ⚠️ "데이터 목록", "데이터의 목록", "데이터 리스트" 처럼 목록 대상이 "데이터"인 경우 → 반드시 "데이터_보유_현황" (축제_목록 아님)
  ⚠️ "확인할 수 있는 축제 목록", "볼 수 있는 축제 목록" 처럼 목록 대상이 "축제"이면 "데이터_보유_현황" 아닌 "축제_목록"으로 분류
  ⚠️ 단, 아래 경우는 반드시 "통계_분석"으로 분류:
     - "방문인구 알려줘", "매출 보여줘" 처럼 특정 지표(방문인구/매출/연령대/성별/시간대/업종)를 직접 요청
     - "방문인구 데이터 알려줘" 처럼 지표명 + "알려줘/보여줘/조회" 조합
     - 지역명/축제명 + 특정 지표(업종/방문인구/매출 등) + "확인할 수 있어?" 조합 → 통계_분석
       (예: "홍천 축제 업종 확인할 수 있어?" → 통계_분석, "이 축제 매출 볼 수 있어?" → 통계_분석)
  ⚠️ 구분 기준: "데이터가 있어?" / "어떤 데이터 있어?" → 데이터_보유_현황 / "업종 확인할 수 있어?" / "데이터 알려줘" → 통계_분석
- "데이터_가이드": 데이터 산출방식, 용어 정의, 계산 방법 등 가이드 문서 기반 답변 요청
  ⚠️ "산출방식", "어떻게 산출", "용어", "유동인구란", "생활인구란", "관내가 뭐" 등 → 반드시 "데이터_가이드"
  ⚠️ "어떻게 계산", "계산 방법", "계산 기준", "어떻게 측정", "기준이 뭐", "무슨 뜻", "어떤 의미", "정의가 뭐", "어떻게 구해", "어떻게 집계" 등 데이터 개념/방법론 질문 → 반드시 "데이터_가이드"
  ⚠️ 구분 기준: 데이터 지표의 '의미·계산법·기준'을 묻는 질문 → "데이터_가이드" / 실제 데이터 수치를 요청하는 질문 → "통계_분석" """

_BOOLEAN_FIELDS = """[불리언 필드 분류 기준]
- is_recent: "최근", "최신", "가장 최근", "마지막", "요즘", "종료된", "끝난", "마감된" 포함 시 true
  ⚠️ "모든/각/전체" + "종료된/끝난/마감된" 조합 시 is_recent=true이지만 is_all_festivals는 질문 의도에 따라 판단
     (예: "종료된 모든 축제 비교" → is_recent=true, is_all_festivals=true)
  ⚠️ "종료된/끝난" 단독(모든/각 없이) → is_recent=true, is_all_festivals=false (최근 종료 1개)
- is_other_festival: "다른 축제", "다른축제", "다른 행사", "다른 보고서", "다른 데이터" 포함 시 true
- is_list_ref: "이 축제들", "이 중에서", "이 행사들", "위 축제들", "그 축제들", "해당 축제들" 포함 시 true
- is_all_festivals: "각 축제", "각각의 축제", "모든 축제", "각 행사", "전체 축제", "축제별", "축제마다", "각각의 행사", "모든 행사", "전 축제" 포함 시 true
  ⚠️ "최근에 진행한 축제", "최근 축제" 처럼 is_recent=true인 경우 is_all_festivals=false (최근 축제 1개를 찾는 것)
  ⚠️ "수원에서 진행한 축제", "홍천읍 축제" 처럼 특정 지역 축제를 찾는 경우 is_all_festivals=false
  ⚠️ "축제 기간 동안", "축제 기간 중", "기간 내", "이 기간" 처럼 특정 축제 기간을 지칭하는 경우 is_all_festivals=false (단일 축제 기간 조회)
  ⚠️ "이 축제", "해당 축제", "그 축제" 처럼 지시어로 단일 축제를 가리키는 경우 is_all_festivals=false
- is_all_festivals_stat: is_all_festivals가 true이면서 "방문인구"/"방문객"/"매출"/"소비"/"유동인구"/"판매"/"결제"/"연령"/"성별"/"시간대" 중 하나 이상 포함 시 true
  ⚠️ is_recent=true이면 is_all_festivals_stat=false (단일 최근 축제 통계 조회)
  ⚠️ 지역명 + "최근에 진행한 축제" + 통계키워드 → is_all_festivals=false, is_all_festivals_stat=false
  ⚠️ "축제 기간 동안/중" + 통계키워드 → is_all_festivals=false, is_all_festivals_stat=false (특정 축제 기간의 상세 통계 조회)"""

_JSON_SCHEMA = """JSON 형식으로만 반환 (다른 텍스트 없이):
{{"region": "지역명 또는 축제명 또는 null", "year": "연도 4자리 또는 null", "specific_date": "YYYYMMDD 또는 null", "month": "MM 또는 null", "intent": "축제_목록|축제_정보|통계_분석|일반_질문|데이터_보유_현황|데이터_가이드", "is_recent": true/false, "is_other_festival": true/false, "is_list_ref": true/false, "is_all_festivals": true/false, "is_all_festivals_stat": true/false}}"""

_INTENT_EXAMPLES = """예시:
- "정조대왕 능행차 성별 소비금액" → {{"region": "정조대왕 능행차", "year": null, "specific_date": null, "month": null, "intent": "통계_분석"}}
- "수원축제 2025년 시간대별 방문인구" → {{"region": "수원", "year": "2025", "specific_date": null, "month": null, "intent": "통계_분석"}}
- "2025 수원화성문화제 방문인구" → {{"region": "수원화성문화제", "year": "2025", "specific_date": null, "month": null, "intent": "통계_분석"}}
- "최근에 수원에서 진행한 축제" → {{"region": "수원", "year": null, "specific_date": null, "month": null, "intent": "축제_목록"}}
- "이 축제 20대 방문인구" (직전 축제: 정조대왕 능행차, 수원시) → {{"region": "정조대왕 능행차", "year": null, "specific_date": null, "month": null, "intent": "통계_분석"}}
- "2025년 화성문화제 매출" → {{"region": "화성문화제", "year": "2025", "specific_date": null, "month": null, "intent": "통계_분석"}}
- "25.10.10 방문객" → {{"region": null, "year": "2025", "specific_date": "20251010", "month": "10", "intent": "통계_분석"}}
- "수원 축제 몇 개야?" → {{"region": "수원", "year": null, "specific_date": null, "month": null, "intent": "축제_목록"}}
- "수원축제 기간 알려줘" → {{"region": "수원", "year": null, "specific_date": null, "month": null, "intent": "축제_정보"}}
- 해당 날짜에 가장 많이 팔린 품목 (직전 답변에 2025년 9월 28일 언급) → {{"region": "화성문화제", "year": "2025", "specific_date": "20250928", "month": "09", "intent": "통계_분석"}}
- 그 날 방문인구 (직전 답변에 20251002 언급) → specific_date: 20251002
- "서울역에서 이 축제까지 어떻게 가?" (직전 축제: 수원화성문화제) → {{"region": "수원화성문화제", "year": null, "specific_date": null, "month": null, "intent": "일반_질문"}}
- "주변 맛집 추천해줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "일반_질문"}}
- "주차장 있어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "일반_질문"}}
- "가장 매출이 높은 연령대는 어디인가요?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석"}}
- "방문인구가 가장 많은 시간대는 어디인가요?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석"}}
- "유동인구가 있는 축제가 있어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "내가 확인할 수 있는 유동인구가 있는 축제가 있어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "방문인구 데이터가 있는 축제 알려줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "내가 확인할 수 있는 축제들의 데이터" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "내가 확인할 수 있는 축제의 데이터는 뭐가 있어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "내가 확인할 수 있는 축제 데이터는 뭐가 있어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "볼 수 있는 축제 데이터 뭐가 있어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "각 축제들에 무슨 데이터들이 있어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "어떤 축제에 어떤 데이터가 있나요?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "보유한 데이터 현황 알려줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "축제의 데이터는 뭐야?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "내가 확인할 수 있는 데이터의 목록" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "확인 가능한 데이터 목록" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "데이터 리스트 보여줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "볼 수 있는 데이터 목록은?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "최근 수원 축제" → {{"region": "수원", "year": null, "specific_date": null, "month": null, "intent": "축제_목록", "is_recent": true, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "다른 축제는 없어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": true, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "각 축제별 방문인구 비교" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": true, "is_all_festivals_stat": true}}
- "유동인구란 무엇인가요?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_가이드", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "방문인구 산출방식 알려줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_가이드", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "유동인구는 어떻게 계산돼?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_가이드", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "방문인구 계산 기준이 뭐야?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_가이드", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "매출은 어떻게 측정해?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_가이드", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "연령대 구분 기준이 뭐야?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_가이드", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "방문인구 데이터 있어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "데이터_보유_현황"}}
- "홍천읍 축제의 업종 전체를 확인할 수 있어?" → {{"region": "홍천읍", "year": null, "specific_date": null, "month": null, "intent": "통계_분석"}}
- "이 축제 업종 볼 수 있어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석"}}
- "이 축제 매출 확인할 수 있어?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석"}}
- "방문인구 데이터 알려줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석"}}
- "수원화성문화제 방문인구 데이터 보여줘" → {{"region": "수원화성문화제", "year": null, "specific_date": null, "month": null, "intent": "통계_분석"}}
- "종료된 수원 축제 알려줘" → {{"region": "수원", "year": null, "specific_date": null, "month": null, "intent": "축제_목록", "is_recent": true}}
- "끝난 축제 방문인구" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": true}}
- "내가 확인할 수 있는 축제 목록 알려줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "축제_목록", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "내가 볼 수 있는 축제 목록" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "축제_목록", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "축제 목록 알려줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "축제_목록", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "내 계정 축제 목록" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "축제_목록", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "조회 가능한 축제 리스트" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "축제_목록", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "이 축제들 중에서 방문인구 높은 건?" (이전 목록 있음) → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": true, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "위 축제들 매출 비교해줘" (이전 목록 있음) → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": true, "is_all_festivals": false, "is_all_festivals_stat": true}}
- "이 중에서 가장 방문객 많은 축제는?" (이전 목록 있음) → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": true, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "그 축제들 연령대별 매출 알려줘" (이전 목록 있음) → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": true, "is_all_festivals": false, "is_all_festivals_stat": true}}
- "해당 축제들 방문인구 순위 알려줘" (이전 목록 있음) → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": true, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "축제별 매출 비교해줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": true, "is_all_festivals_stat": true}}
- "홍천읍에서 최근에 진행한 축제 연령대별 매출 알려줘" → {{"region": "홍천읍", "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": true, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "수원에서 최근 축제 방문인구 알려줘" → {{"region": "수원", "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": true, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "최근에 진행한 축제 성별 매출 알려줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": true, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "수원화성문화제 기간 알려줘" → {{"region": "수원화성문화제", "year": null, "specific_date": null, "month": null, "intent": "축제_정보", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "이 축제 언제야?" (직전 축제: 정조대왕 능행차) → {{"region": "정조대왕 능행차", "year": null, "specific_date": null, "month": null, "intent": "축제_정보", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "수원화성문화제 기간이랑 방문인구 알려줘" → {{"region": "수원화성문화제", "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "9월 수원 축제" → {{"region": "수원", "year": null, "specific_date": null, "month": "09", "intent": "축제_목록", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "축제 기간 동안 시간대별 성별 방문인구는?" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "축제 기간 중 연령대별 매출 알려줘" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "이 기간 동안 시간대별 방문인구" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
- "기간 내 성별 매출 비교" → {{"region": null, "year": null, "specific_date": null, "month": null, "intent": "통계_분석", "is_recent": false, "is_other_festival": false, "is_list_ref": false, "is_all_festivals": false, "is_all_festivals_stat": false}}
  ⚠️ 핵심 판단: "축제의 목록/리스트/개수" → "축제_목록", "축제의 데이터/통계/자료" → "데이터_보유_현황" """

# Context Cache에 등록되는 STEP1 정적 규칙
_EXTRACT_STATIC_CONTENT = (
    "이전 대화 맥락을 참고하여 현재 질문에서 검색 키워드(지역명 또는 축제명)와 날짜 정보를 추출하세요.\n\n"
    + _EXTRACTION_RULES
    + "\n\n"
    + _INTENT_CRITERIA
    + "\n\n"
    + _BOOLEAN_FIELDS
    + "\n\n"
    + _JSON_SCHEMA
    + "\n\n"
    + _INTENT_EXAMPLES
)

# ─────────────────────────────────────────────────────────────────────────────


def prompt_extract_festival_context(
    history_section: str,
    festival_hint: str,
    question: str,
    current_year: int,
    current_month: int,
) -> str:
    """이전 대화에서 축제/지역/날짜 컨텍스트 추출"""
    year_hint = f"(올해={current_year}, 작년={current_year - 1}, 재작년={current_year - 2}, 이번 달={current_month:02d})"
    return (
        f"이전 대화 맥락을 참고하여 현재 질문에서 검색 키워드(지역명 또는 축제명)와 날짜 정보를 추출하세요.\n"
        f"{history_section}{festival_hint}\n"
        f"[현재 질문]\n{question}\n"
        f"[연도 참고] {year_hint}\n\n"
        f"{_EXTRACTION_RULES}\n\n"
        f"{_INTENT_CRITERIA}\n\n"
        f"{_BOOLEAN_FIELDS}\n\n"
        f"{_JSON_SCHEMA}\n\n"
        f"{_INTENT_EXAMPLES}"
    )


def prompt_extract_dynamic(
    history_section: str,
    festival_hint: str,
    question: str,
    current_year: int,
    current_month: int,
) -> str:
    """Context Cache 사용 시 동적 부분만 반환 (정적 규칙은 캐시에 포함됨)"""
    year_hint = f"(올해={current_year}, 작년={current_year - 1}, 재작년={current_year - 2}, 이번 달={current_month:02d})"
    return (
        f"{history_section}{festival_hint}\n"
        f"[현재 질문]\n{question}\n"
        f"[연도 참고] {year_hint}\n\n"
        f"JSON 형식으로만 반환하세요. 필드: region, year, month, specific_date, intent, is_recent, is_other_festival, is_list_ref, is_all_festivals, is_all_festivals_stat"
    )


def prompt_summarize_history(messages: list[dict]) -> str:
    """긴 대화 이력을 구조화된 JSON으로 요약 (히스토리 압축용)"""
    lines = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "user":
            lines.append(f"사용자: {content}")
        elif role == "assistant":
            lines.append(f"어시스턴트: {content}")
    return (
        "다음 대화 이력을 분석하여 아래 JSON 스키마에 맞게 정확히 반환하세요.\n"
        "반드시 순수 JSON만 반환하세요. ```json 코드블록, 설명, 추가 텍스트 없이 JSON만 반환하세요.\n\n"
        "[출력 스키마]\n"
        "{\n"
        '  "festival": "축제명 (없으면 null)",\n'
        '  "reprt_id": 숫자 또는 null,\n'
        '  "year": "YYYY 형식 연도 문자열 또는 null",\n'
        '  "last_intent": "통계_분석 | 축제_목록 | 축제_정보 | 데이터_보유_현황 | 데이터_가이드 | 일반_질문 | null",\n'
        '  "queried": ["방문인구", "성별_매출"],\n'
        '  "specific_dates": ["YYYYMMDD"]\n'
        "}\n\n"
        "[필드 설명]\n"
        "- festival: 대화에서 언급된 축제명 (없으면 null)\n"
        "- reprt_id: 축제의 reprt_id 숫자 (언급되지 않았으면 null)\n"
        "- year: 조회 연도 (없으면 null)\n"
        "- last_intent: 마지막 사용자 의도 (통계_분석, 축제_목록, 축제_정보, 데이터_보유_현황, 데이터_가이드, 일반_질문 중 하나, 없으면 null)\n"
        "- queried: 대화에서 조회된 데이터 지표 목록 (없으면 빈 배열)\n"
        "  예시 값: '방문인구', '성별_매출', '시간대별_방문', '연령대별_소비', '업종별_매출', '유입지_방문인구', '생활인구', '거주인구', '직장인구'\n"
        "- specific_dates: 언급된 특정 날짜 목록 YYYYMMDD 형식 (없으면 빈 배열)\n\n"
        "[대화 이력]\n"
        + "\n".join(lines)
        + "\n\nJSON:"
    )


def prompt_pick_best_festival(question: str, candidates: str, prev_hint: str) -> str:
    """여러 축제 후보 중 가장 적합한 것을 선택"""
    return f"""다음 축제 목록 중 아래 질문에 가장 적합한 축제의 reprt_id를 숫자만 반환하세요.

[질문]
{question}
{prev_hint}
[축제 목록]
{candidates}

[선택 기준 - 우선순위 순]
1. 질문에 특정 축제명이 명시된 경우 → 해당 축제명과 가장 유사한 것 선택
2. 지시어만 있고 직전 축제가 있는 경우 → 직전 축제의 reprt_id 선택
3. "수원축제 2025년도", "수원축제 2025년" 처럼 연도만 있고 구체적 축제명이 없는 경우 → "수원시 3대 축제" 선택
4. 질문에 특정 장소(화성행궁, 행궁광장 등)가 명시된 경우 → 그 장소 관련 축제 선택
5. 질문이 "축제 전체" 또는 포괄적인 경우 → "연계포함" 또는 범위가 넓은 축제 선택
6. 단순 지역명만 있는 경우(수원시, 수원역인근 등)보다 구체적 축제명 우선
7. 분석 요청(상권, 영역, 구간 등 지역 분석)은 해당 지역/상권 관련 항목 선택

reprt_id 숫자만 반환 (다른 텍스트 없이):"""


# Context Cache에 등록되는 정적 규칙 (테이블 목록과 함께 캐싱됨)
_DECOMPOSE_STATIC_RULES = """[테이블 선택 규칙]
1. ⚠️ **절대 선택 금지 테이블:**
   - tb_analysis_report : 축제 메타데이터 전용 (통계 데이터 없음)
   - tb_cnsmp_amount, tb_tmzon_cnsmp_amount : 데이터 갱신 중단
   - 날짜 접미어가 붙은 테이블 (예: tb_agrde_selng_20260223, tb_visit_popltn_20251201 등)
     → 이름에 8자리 날짜(YYYYMMDD)가 포함된 테이블은 임시/백업 테이블이므로 선택 금지
     → 날짜 접미어 없는 기본 테이블(tb_agrde_selng, tb_agrde_visit_popltn 등)을 사용할 것
   - tb_svc_induty_sclas, tb_svc_induty_lclas : JOIN 전용 코드 테이블 (독립 선택 금지)
   - tb_agrde_main_selng_induty_rank_sm, tb_nation_main_selng_induty_rank_sm : 데이터 없음 (갱신 중단) - 절대 선택 금지
     → 업종 질문 시 tb_selng_org 또는 *_selng 계열 테이블 사용할 것
   - tb_sido, tb_cty, tb_thrd, tb_admi, tb_cd_info : 지역코드 참조 테이블 (독립 선택 금지)

2. **질문 유형별 필수 테이블:**
   - "방문인구" 또는 "방문객" 질문 → 반드시 *_visit_popltn 계열 선택
     기본(차원 미지정): tb_visit_popltn (전체 방문인구)
     연령대 분석 요청 시: tb_agrde_visit_popltn
     성별 분석 요청 시: tb_sexdstn_visit_popltn
     시간대 분석 요청 시: tb_tmzon_visit_popltn
     유입지 분석 요청 시: tb_inflow_visit_popltn
   - "매출" 또는 "소비금액" 질문 → 반드시 *_selng 계열 선택
   - "업종", "잘 팔린 업종", "많이 팔린 업종", "인기 업종", "매출 업종", "업종별 매출", "업종 순위" 질문
     → tb_selng_org (매출데이터 원본, 삼성카드 데이터)
     → ⚠️ 이 테이블은 tb_samsungcard_region_cd_mapng JOIN으로 reprt_id 필터링
     → tco_tobz_nm(업종명), tot_amt(총매출액), tot_cnt(총건수) 컬럼 사용
     → apr_dt 컬럼으로 날짜 필터링 (YYYYMMDD 형식)
   - "연령별 업종", "연령대별 소비 업종", "연령대별 인기 업종", "나이대별 업종" 질문
     → tb_selng_org (연령대별 승인금액비율 컬럼 활용)
     → ⚠️ 절대 tb_agrde_selng 사용 금지 (업종 정보 없음)
   - "내외국인별 업종", "내외국인 소비 업종", "내국인/외국인 업종" 질문
     → tb_nation_selng (내/외국인 매출 데이터)
   - "생활인구", "유동인구(행정)" 질문 → tb_dayt_popltn (전체), tb_tmzon_dayt_popltn (시간대별)
     → ⚠️ 이 테이블은 admi_cd 기준 필터링 (reprt_id 아님)
  ⚠️ 유동인구 의미 구분:
     - "생활인구", "유동인구(행정)", "행정 유동인구" → tb_dayt_popltn (admi_cd 기준)
     - "방문객", "방문인구", "방문자" 의미의 유동인구 → tb_visit_popltn 계열 (reprt_id 기준)
     - 문맥상 축제 방문자를 가리키면 반드시 *_visit_popltn 사용
   - "거주인구", "거주자", "상주인구" 질문 → tb_reside_popltn
     → ⚠️ 이 테이블은 admi_cd 기준 필터링
   - "직장인구", "직장인", "재직자" 질문 → tb_wrc_popltn
     → ⚠️ 이 테이블은 admi_cd 기준 필터링
   - "관심지역", "방문 희망 지역", "방문 의향", "어디서 왔나" 질문 → tb_intrst_region (요약), tb_intrst_region_relm (연관지역 상세)
     → ⚠️ 이 테이블은 reprt_id 기준 필터링

3. **테이블명 패턴:**
   - tb_agrde_* : 연령대별 (10대, 20대, 30대...)
   - tb_sexdstn_* : 성별 (남성, 여성)
   - tb_tmzon_* : 시간대별 (0시~23시)
   - tb_nation_* : 내/외국인
   - tb_inflow_* : 유입지 (어디서 왔는지)
   - tb_intrst_region* : 관심지역 / 방문 의향 분석
   - *_visit_popltn : 방문인구 수치
   - *_selng : 매출/소비금액 수치
   - *_dayt_popltn : 생활인구 (admi_cd 기준 필터)
   - *_reside_popltn : 거주인구 (admi_cd 기준 필터)
   - *_wrc_popltn : 직장인구 (admi_cd 기준 필터)

4. **복합 조건 처리:**
   - 연령대 + 방문인구 → tb_agrde_visit_popltn
   - 연령대 + 업종/소비업종 → tb_selng_org (연령대별 승인금액비율 컬럼 활용, tb_agrde_selng 금지)
   - 성별 + 매출 → tb_sexdstn_selng
   - 시간대 + 방문인구 → tb_tmzon_visit_popltn
   - 내/외국인 + 매출/소비 → tb_nation_selng
   - 여러 조건 → 각각의 테이블 모두 선택

5. **⚠️ 존재하지 않는 교차 조합 (DB에 해당 테이블 없음):**
   아래 조합은 단일 테이블에 존재하지 않습니다. 이런 질문이 들어오면 **테이블을 선택하지 말고** 빈 문자열을 반환하세요.
   - 유입지(관내/인접/관외) × 연령대별 방문인구 → 불가 (예: "인접 지역 방문인구의 연령대", "관내 방문객 나이대")
   - 유입지(관내/인접/관외) × 성별 방문인구 → 불가
   - 유입지(관내/인접/관외) × 시간대별 → 불가
   - 내/외국인 × 연령대별 방문인구 → 불가 (예: "외국인 방문인구 중 20대 비율")
   - 내/외국인 × 성별 방문인구 → 불가
   단, 각 차원 단독 조회는 가능 (유입지만: tb_inflow_visit_popltn / 연령대만: tb_agrde_visit_popltn)

[예시]
- 질문: "방문인구는?" → tb_visit_popltn
- 질문: "20대 방문인구는?" → tb_agrde_visit_popltn
- 질문: "시간대별 방문인구는?" → tb_tmzon_visit_popltn
- 질문: "남녀 매출은?" → tb_sexdstn_selng
- 질문: "매출이 잘나온 업종을 알려줘" → tb_selng_org
- 질문: "업종별 매출 순위는?" → tb_selng_org
- 질문: "인기 업종은?" → tb_selng_org
- 질문: "연령별 주요 소비 업종은?" → tb_selng_org
- 질문: "내외국인별 주요 소비 업종은?" → tb_nation_selng
- 질문: "생활인구는?" → tb_dayt_popltn
- 질문: "시간대별 생활인구는?" → tb_tmzon_dayt_popltn
- 질문: "거주인구는?" → tb_reside_popltn
- 질문: "직장인구는?" → tb_wrc_popltn
- 질문: "관심지역 현황은?" → tb_intrst_region
- 질문: "방문 의향 연관 지역은?" → tb_intrst_region_relm

필요한 테이블명을 쉼표로 구분해서 반환 (설명 없이 테이블명만):
예시) tb_sexdstn_visit_popltn,tb_tmzon_selng"""


def prompt_decompose_question(question: str, table_count: int, tables_summary: str) -> str:
    """질문에 필요한 테이블 목록 선택 (Context Cache 미사용 fallback용)"""
    return (
        f"당신은 데이터베이스 전문가입니다.\n\n"
        f"[질문]\n{question}\n\n"
        f"[사용 가능한 테이블 목록 ({table_count}개)]\n{tables_summary}\n\n"
        f"{_DECOMPOSE_STATIC_RULES}"
    )


def prompt_generate_sql(
    table_schema: str,
    festival_name: str,
    filter_col: str,
    filter_val: str,
    date_desc: str,
    date_condition: str,
    group_by_hint: str,
    question: str,
    db_schema: str,
    table: str,
) -> str:
    """테이블 1개에 대한 SQL 생성"""
    return f"""당신은 PostgreSQL 전문가입니다.

[테이블 스키마]
{table_schema}

[축제 컨텍스트]
- 축제명: {festival_name}
- {filter_col.upper()}: {filter_val}  ← 이 값으로 관심지역을 필터링합니다
- {date_desc}

[사용자 질문]
{question}

[SQL 규칙]
1. 테이블 참조: "{db_schema}"."{table}"
2. WHERE 조건 필수:
   - {filter_col} = '{filter_val}'
   - {date_condition}
3. 질문에서 이 테이블과 관련된 조건만 추출해 SELECT/WHERE 작성
   (예: tb_tmzon_visit_popltn이면 t6_vipop ~ t23_vipop 컬럼 사용)
   (예: tb_tmzon_selng이면 t6_salamt ~ t23_salamt 컬럼 사용)
   (예: tb_sexdstn_visit_popltn이면 mvipop(남성), fvipop(여성) 컬럼 사용)
   (예: tb_sexdstn_selng이면 mdcnt, fdcnt, msalamt, fsalamt 컬럼 사용)
   (예: tb_nation_selng이면 내/외국인별 매출 데이터,
        반드시 "{db_schema}"."tb_svc_induty_sclas" i JOIN하여 업종명(svc_induty_sclas_cd_nm) 표시,
        JOIN 조건: n.svc_induty_sclas_cd = i.svc_induty_sclas_cd,
        SELECT i.svc_induty_sclas_cd_nm AS "업종명", SUM(n.native_salamt) AS "내국인_매출", SUM(n.frgnr_salamt) AS "외국인_매출", SUM(n.tot_salamt) AS "총매출" GROUP BY i.svc_induty_sclas_cd_nm ORDER BY SUM(n.tot_salamt) DESC LIMIT 10,
        WHERE n.reprt_id = {filter_val} 조건 필수
        ⚠️ tb_nation_selng은 항상 reprt_id로 필터링: WHERE n.reprt_id = {filter_val}
           (filter_col이 admi_cd여도 이 테이블은 예외적으로 reprt_id 컬럼 사용))
   (예: tb_selng_org이면 tco_tobz_nm(업종명), tot_amt(총매출액), tot_cnt(총건수) 컬럼 사용,
        반드시 FROM "{db_schema}"."tb_selng_org" s JOIN "{db_schema}"."tb_samsungcard_region_cd_mapng" m ON s.inqr_ak_bur_c = m.inqr_ak_bur_c AND s.inqr_tery_dv_c = m.inqr_tery_dv_c 패턴 사용,
        WHERE m.reprt_id = {filter_val} AND s.apr_dt BETWEEN '시작일' AND '종료일'
        ⚠️ apr_dt는 YYYYMMDD 형식 문자열. date_condition의 stdr_ymd 조건을 apr_dt 컬럼으로 변환하여 적용.
           예: stdr_ymd BETWEEN '20260101' AND '20260131' → apr_dt BETWEEN '20260101' AND '20260131',
        GROUP BY s.tco_tobz_nm ORDER BY SUM(tot_amt) DESC LIMIT 10)
   (예: tb_selng_org에서 연령대별 소비 업종 조회 시:
        각 연령대별 매출 = SUM(tot_amt * 해당연령대_비율컬럼 / 100) 으로 계산,
        연령대별 비율 컬럼: man_er20_apr_am_rt(남자20대), fmle_er20_apr_am_rt(여자20대), man_er30_apr_am_rt(남자30대), fmle_er30_apr_am_rt(여자30대), man_er40_apr_am_rt(남자40대), fmle_er40_apr_am_rt(여자40대), man_er50_apr_am_rt(남자50대), fmle_er50_apr_am_rt(여자50대), man_er60_apr_am_rt(남자60대), fmle_er60_apr_am_rt(여자60대),
        SELECT tco_tobz_nm AS "업종명",
               ROUND(SUM(tot_amt * (COALESCE(man_er20_apr_am_rt,0) + COALESCE(fmle_er20_apr_am_rt,0)) / 100)) AS "20대_매출",
               ROUND(SUM(tot_amt * (COALESCE(man_er30_apr_am_rt,0) + COALESCE(fmle_er30_apr_am_rt,0)) / 100)) AS "30대_매출",
               ROUND(SUM(tot_amt * (COALESCE(man_er40_apr_am_rt,0) + COALESCE(fmle_er40_apr_am_rt,0)) / 100)) AS "40대_매출",
               ROUND(SUM(tot_amt * (COALESCE(man_er50_apr_am_rt,0) + COALESCE(fmle_er50_apr_am_rt,0)) / 100)) AS "50대_매출",
               ROUND(SUM(tot_amt * (COALESCE(man_er60_apr_am_rt,0) + COALESCE(fmle_er60_apr_am_rt,0)) / 100)) AS "60대_매출",
               ROUND(SUM(tot_amt)) AS "전체_매출"
        FROM ... JOIN ... WHERE ... GROUP BY tco_tobz_nm ORDER BY SUM(tot_amt) DESC LIMIT 10)
   (예: tb_intrst_region이면 방문 의향/관심지역 데이터,
        reprt_id 기준 필터링: WHERE reprt_id = {filter_val},
        sido_nm(시도명), cty_nm(시군구명), visit_intnt_popltn(방문의향인구), rank(순위) 등 컬럼 사용,
        SELECT sido_nm AS "시도", cty_nm AS "시군구", SUM(visit_intnt_popltn) AS "방문의향인구" GROUP BY sido_nm, cty_nm ORDER BY SUM(visit_intnt_popltn) DESC LIMIT 10)
   (예: tb_dayt_popltn이면 생활인구 데이터,
        admi_cd 기준 필터링: WHERE admi_cd = '{filter_val}',
        tot_dayt_popltn(전체생활인구), male_dayt_popltn(남성생활인구), female_dayt_popltn(여성생활인구) 등 컬럼 사용,
        SELECT stdr_ymd AS "기준일자", SUM(tot_dayt_popltn) AS "전체생활인구" GROUP BY stdr_ymd ORDER BY stdr_ymd)
   (예: tb_reside_popltn이면 거주인구 데이터, admi_cd 기준 필터링)
   (예: tb_wrc_popltn이면 직장인구 데이터, admi_cd 기준 필터링)
4. {group_by_hint}
5. 시간대별 전체 합계 조회 시:
   - SELECT SUM(t6_vipop) AS "6시_방문인구", SUM(t7_vipop) AS "7시_방문인구", ... SUM(t23_vipop) AS "23시_방문인구"
   - 또는 SELECT SUM(t6_salamt) AS "6시_매출", SUM(t7_salamt) AS "7시_매출", ... SUM(t23_salamt) AS "23시_매출"
   - GROUP BY 없이 전체 합산
   - stdr_ymd 포함하지 않음
6. 일별 데이터 조회 시:
   - SELECT stdr_ymd, SUM(컬럼) AS "한글_별칭"
   - 별칭은 반드시 한글로 작성 (예: "내국인_방문객", "외국인_방문객", "전체_방문객", "남성_방문인구", "여성_방문인구", "남성_매출", "여성_매출")
   - GROUP BY stdr_ymd
   - ORDER BY stdr_ymd
   - **HAVING 절 사용 금지**
7. 요일별 데이터 조회 시 (요일별 집계):
   - **TO_CHAR(stdr_ymd::date, 'Day') 절대 금지** — 영어 요일명(Sunday, Monday...) 반환됨
   - 반드시 CASE 문으로 한글 요일명 변환:
     ```
     CASE EXTRACT(DOW FROM stdr_ymd::date)
       WHEN 0 THEN '일요일'
       WHEN 1 THEN '월요일'
       WHEN 2 THEN '화요일'
       WHEN 3 THEN '수요일'
       WHEN 4 THEN '목요일'
       WHEN 5 THEN '금요일'
       WHEN 6 THEN '토요일'
     END AS "요일"
     ```
   - GROUP BY EXTRACT(DOW FROM stdr_ymd::date)
   - ORDER BY EXTRACT(DOW FROM stdr_ymd::date)
   - 예시: SELECT CASE EXTRACT(DOW FROM stdr_ymd::date) WHEN 0 THEN '일요일' WHEN 1 THEN '월요일' WHEN 2 THEN '화요일' WHEN 3 THEN '수요일' WHEN 4 THEN '목요일' WHEN 5 THEN '금요일' WHEN 6 THEN '토요일' END AS "요일", SUM(tot_amt) AS "총매출액" FROM ... WHERE ... GROUP BY EXTRACT(DOW FROM stdr_ymd::date) ORDER BY EXTRACT(DOW FROM stdr_ymd::date)
8. 단일 집계 시: SUM(컬럼)만 사용
9. **모든 컬럼 별칭(AS)은 반드시 한글로 작성** — 영어 alias 금지
10. 주석 없이 SQL만 반환

**중요:** WHERE 절로 기간을 필터링한 후, 적절한 GROUP BY 사용. HAVING으로 특정 날짜를 선택하지 마세요.

SQL:"""


def prompt_fix_sql(sql: str, error: str, filter_hint: str, db_schema: str, table: str) -> str:
    """오류난 SQL 자동 수정"""
    return f"""SQL 오류 수정:

원본 SQL:
{sql}

오류:
{error}

수정 규칙:
- 테이블 참조: "{db_schema}"."{table}"
- {filter_hint}
- stdr_ymd는 'YYYYMMDD' 형식
- HAVING 절 사용 금지

수정된 SQL만 반환."""


def prompt_combined_answer(
    question: str,
    festival_name: str,
    date_info: str,
    results_text: str,
    change_instruction: str,
    prev_analysis_section: str,
) -> str:
    """다중 테이블 조회 결과를 통합하여 자연어 답변 생성"""
    return f"""질문: {question}

축제: {festival_name} ({date_info})
{prev_analysis_section}
각 테이블 조회 결과:
{results_text}

[답변 작성 규칙]
1. 각 테이블 결과를 독립적인 수치로 명확하게 제시하세요.
2. 금액은 반드시 천 단위 콤마 숫자에 "원" 단위를 붙여 표시 (예: 1,000,000원, 37,381,600,000원) — 억/만/천 단위 한글 변환 금지
3. 마크다운 테이블 또는 리스트로 깔끔하게 정리
4. 시간대별 데이터는 6시~23시까지 모든 시간대를 빠짐없이 표시
5. 짧고 명확하게 (불필요한 주의/면책 문구 없이)
6. 비율(%)을 계산할 때는 반드시 (개별값 ÷ 전체합계 × 100)으로 계산하고, 모든 항목의 비율 합계가 100%가 되어야 합니다.
7. **데이터 불일치 감지:** 사용자가 요청한 분석 차원이 조회 결과에 없는 경우 (예: "인접 지역별 연령대" 요청인데 결과에 유입지 구분이 없는 경우), 절대로 관련 없는 데이터를 억지로 답변하지 마세요. 대신 아래 형식으로 안내하세요:
   > "요청하신 **[요청 분석명]** 데이터는 현재 제공되지 않습니다.
   > 제공 가능한 유사 데이터: [가능한 대안 목록]"
   예시:
   - "인접 지역 방문인구의 연령대" 요청 → "유입지별×연령대 교차 데이터가 없습니다. 제공 가능: 유입지별 방문인구(관내/인접/관외) 또는 연령대별 전체 방문인구"
   - "외국인 방문인구 중 연령대" 요청 → "내외국인×연령대 교차 데이터가 없습니다. 제공 가능: 내/외국인별 방문인구 또는 연령대별 전체 방문인구"
{change_instruction}

답변:"""


def prompt_data_guide_answer(question: str, guide_content: str) -> str:
    """데이터 산출방식/용어 질문에 대한 가이드 문서 기반 답변"""
    return f"""당신은 축제 데이터 분석을 도와주는 AI 챗봇입니다.
아래 [데이터 산출방식 문서]를 참고하여 사용자의 질문에 답변하세요.

[데이터 산출방식 문서]
{guide_content}

[질문]
{question}

[답변 규칙]
1. 문서에 있는 내용만 답변하세요. 문서에 없는 내용은 "문서에서 확인할 수 없는 내용입니다"라고 안내하세요.
2. 마크다운 형식으로 깔끔하게 정리하세요.
   - 제목은 ### 헤더를 사용하세요.
   - 항목 나열은 - 또는 숫자 목록을 사용하세요.
   - ⚠️ 한국어 문장 중간에 **굵게** 표시를 절대 사용하지 마세요. 예: ~~"인구는 **매일** 집계됩니다"~~ (금지)
   - 굵게 강조가 필요하면 반드시 줄 앞에 **항목명:** 형식으로만 사용하세요. 예: **집계 방식:** 매일 집계
3. 관련 수식이나 예시가 문서에 있으면 함께 제시하세요.
4. 짧고 명확하게 답변하세요.

답변:"""


def prompt_suggested_question(
    question: str,
    answer: str,
    festival_nm: str | None = None,
    festival_period: str | None = None,
    queried_kr: list[str] | None = None,
) -> str:
    """대화 맥락에 맞는 추천 후속 질문 1개 생성"""
    festival_section = ""
    if festival_nm:
        period_str = f" ({festival_period})" if festival_period else ""
        festival_section = f"\n[축제 정보]\n  {festival_nm}{period_str}\n"

    queried_section = ""
    if queried_kr:
        queried_section = f"\n[이미 조회한 데이터]\n  {', '.join(queried_kr)}\n"

    queried_rule = ""
    if queried_kr:
        queried_rule = "\n- 이미 조회한 데이터와 다른 차원(시간대별, 유입지별 등)을 우선 추천"

    return f"""사용자의 질문과 AI의 답변을 바탕으로, 사용자가 다음에 궁금해할 만한 후속 질문을 딱 1개만 생성하세요.

[사용자 질문]
{question}

[AI 답변 요약]
{answer[:500]}
{festival_section}{queried_section}
[규칙]
- 질문 1개만 출력 (설명, 번호, 따옴표 없이 질문 문장만)
- 답변 내용과 자연스럽게 이어지는 구체적인 질문{queried_rule}
- 축제 데이터 분석과 관련된 질문으로 한정
- 30자 이내의 간결한 질문

질문:"""

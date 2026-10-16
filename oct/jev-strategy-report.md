# Jev 전략 보고서: 등장 배경, 현재, 미래, 그리고 우리의 활용

## 1. 보고 개요

- 작성일: 2026-10-16
- 보고 목적: TypeSafe AI의 Jev를 기준으로 결정 모델(System One) 시장의 등장 배경, 현재 상황, 앞으로의 방향을 정리한다. 다른 기업이 왜 이렇게 빨리 비슷한 모델을 내는지 분석하고, 차별화 전략과 우리 브라우저 에이전트에 적용할 방법을 제안한다.
- 선행 문서: [Jev·Jev-like 결정 모델 구조와 업계 현황](jev-decision-model-landscape-report.md). BERT와 `[MASK]`, Laya 구조의 상세 설명은 그 문서 5–6장을 본다.
- 조사 방식: 창업자 인터뷰(Latent Space), 기술 보도(InfoQ, TechCrunch), 모델 카드, 2차 분석 글을 확인했다. 실험은 하지 않았다.
- 문서 상태: 8장 미래 예측과 10장 적용안은 판단과 가설이다. 신뢰도를 함께 표기한다.

## 2. 한 줄 결론

Jev의 핵심은 새 아키텍처가 아니라 **"LLM을 대화 상대가 아니라 코드가 호출하는 타입 있는 부품으로 쓰자"는 제품 정의**다. 이 정의와 인터페이스는 한 달 만에 OpenAI, Amazon과 수십 개 오픈 프로젝트가 따라왔다. 구조가 공개 지식이고, 오픈 백본이 강하고, 확률을 돌려주는 API는 증류 신호가 풍부하기 때문이다. 앞으로 결정 엔드포인트는 모든 LLM 제공자의 기본 기능이 되고, 경쟁 축은 속도·가격에서 **보정 품질, 강건성, 버전 안정성, 도메인 데이터**로 옮겨갈 것이다.

우리는 모델을 만들 이유가 없다. 대신 에이전트 안의 판단을 타입 있는 결정으로 분해하고, 어떤 백엔드든 꽂을 수 있는 **결정 포트**와 **브라우저 도메인 평가셋**을 만들어야 한다. 이것이 우리가 가져갈 수 있는 해자다.

## 3. 등장 배경

### 3.1 풀려던 문제: LLM은 소프트웨어 부품으로 불편하다

에이전트와 자동화가 늘면서 프로그램 안에 작은 판단이 수없이 생겼다. "이 메일은 어느 부서로 보내나", "이 도구 호출은 안전한가", "이 작업은 끝났나" 같은 것들이다. 이런 판단을 채팅 LLM에 맡기면 문제가 생긴다.

| 문제 | 내용 |
|---|---|
| 느리고 비싸다 | 답 한 단어를 위해 토큰을 생성하고, 추론 모델은 생각 토큰까지 쓴다 |
| 형식이 깨진다 | JSON을 요청하고 파싱하고, 깨지면 재시도해야 한다 |
| 확률을 모른다 | 고른 답만 나오고 얼마나 확신하는지 모른다. RLHF는 "그럴듯한 답"으로 분포를 무너뜨린다(mode collapse) |
| 거절한다 | 안전 정렬 때문에 정상 요청도 거절한다. 창업자는 이를 "API에서의 타입 오류"라고 부른다 |
| 버전이 흔들린다 | 같은 별칭 뒤의 모델이 바뀌면 코드 변경 없이 동작이 바뀐다 |

### 3.2 창업자의 문제의식

- Diogo Almeida는 OpenAI에서 InstructGPT(RLHF) 논문을 함께 썼다. 그는 프론티어 모델이 대화에 맞춰 튜닝되면서 소프트웨어 부품으로서의 신뢰성을 잃었다고 본다.
- 핵심 표어는 **"Prod, not God"**이다. 지능은 동료나 챗봇이 아니라 데이터베이스나 정규식처럼 소프트웨어 안으로 사라지는 부품이어야 한다는 뜻이다.
- 출력의 소비자가 사람이 아니라 코드다. 그래서 출력이 `choice`(switch/enum), `score`(임계값/정렬), `noul`(if문)처럼 프로그램 분기에 바로 쓰이는 타입이다.
- "System One"은 카너먼의 『생각에 관한 생각』에서 가져온 이름이다. 빠르고 직관적인 판단(System 1)을 맡고, 느리고 신중한 추론(System 2)은 다른 곳에 맡긴다는 의미다.

### 3.3 기술적 전사: 새로운 아이디어가 아니라 재조합

Jev류가 하는 일 자체는 오래된 문제다.

| 시기 | 접근 | 한계 |
|---|---|---|
| 2018– | BERT 분류기 파인튜닝. `[CLS]` 벡터에 분류 head | 과제마다 라벨 고정, 학습 데이터 필요 |
| 2019– | NLI 기반 zero-shot 분류. "이 글은 X에 관한 것이다"를 함의 판정 | 느리고 보정 안 됨 |
| 2019– | BERT multiple-choice head. 선택지마다 점수를 내고 softmax | 과제별 학습 필요 |
| 2023– | LLM + structured output / constrained decoding | 느리고 확률 없음 |
| 2024– | GLiNER류. 라벨을 입력에 넣어 한 번에 점수 | 개체 인식 중심 |
| **2026-09** | **Jev**: 범용 사전학습 지능 + 요청 시 정의하는 닫힌 답 공간 + 보정을 목표로 한 RL | — |

새로운 점은 세 가지의 조합이다. 하나, **답 공간을 요청 시 정의**해서 재학습 없이 아무 판단에나 쓴다. 둘, **확률 보정 자체를 학습 목표**로 둔다(RLCD). 셋, 이것을 범용 API로 제품화했다.

### 3.4 왜 2026년 9월이었나

- **수요**: 에이전트 한 번 실행에 판단 스텝이 수십 개씩 생긴다. 판단마다 LLM을 부르면 비용과 지연이 쌓인다.
- **백본**: Qwen3.5 같은 오픈 모델이 작은 크기에서도 충분히 똑똑해졌다.
- **학습 기법**: GRPO류 RL과 proper scoring rule 보상은 이미 알려진 도구다.
- **서빙**: prefix caching으로 state를 한 번 읽고 여러 질문을 분기시키는 서빙 기법이 일반화됐다.

## 4. 기본 구조 한눈에

결정 모델의 구현은 세 갈래다. 공통점은 **생성 루프 없이 한 번의 pass로 선택지별 점수를 읽는다**는 것이다.

| 계열 | 방식 | 대표 | 특징 |
|---|---|---|---|
| 인코더 마커 점수 | BERT류 양방향 인코더. 선택지 앞에 `[MASK]`를 붙이고 그 위치 벡터로 점수 | Laya, Von, OpenDecider-nano | 작고 빠름(CPU 15–40ms). 세상 지식과 문맥 길이가 부족 |
| LLM 로짓 읽기 | 디코더 LLM에 선택지를 A/B/C로 붙이고, 답 위치에서 문자별 다음 토큰 확률을 읽음. LoRA로 보정 학습 | Kev, Nimble, JevK5, OpenDecider-small | 똑똑함. 문자 26개 한계는 선택지 log-likelihood로 우회 |
| 학습 없는 방식 | 기존 LLM의 로짓을 그대로 읽음 | SemIf, LitJev | 학습 비용 0. 보정은 따로 맞춰야 함 |

여러 질문을 처리하는 방법도 두 가지다.

- **질문마다 별도 시퀀스**(Laya): 단순하지만 state를 질문 수만큼 반복해서 읽는다. 질문이 늘면 지연도 는다.
- **KV cache prefix 재사용**: state를 한 번 prefill하고 모든 질문이 같은 캐시에서 분기한다. 지연이 질문 수와 거의 무관하다. 창업자도 "state 비용은 한 번만 낸다"고 말한다. 2차 분석은 Jev가 이 방식이라고 보지만, TypeSafe가 공식 확인한 내용은 아니다.

## 5. 현재 (2026-10 기준)

### 5.1 한 달간의 타임라인

| 날짜 | 사건 |
|---|---|
| 09-15 | TypeSafe AI, Jev 공개. $40M 투자 |
| 출시 이틀째 | Vercel AI Gateway 연동. 24시간 안에 유료 팀 약 13%가 사용 |
| 09-25 | LAVOIR 논문. Laya에 "무엇을 되물을지" 판단을 추가 |
| 09-29 | OpenAI, DevDay에서 Decisions API 발표 (Jev 공개 14일 뒤) |
| 10-01 | Amazon(AWS Strands Labs), Strands Decider 2B 오픈소스 공개 |
| 10-06 | OpenAI Decisions API 공개 베타. `gpt-6-luna` 단일 모델, 입력 토큰만 과금 |
| 10-08 | AutoTrust JEV-27B-VL, HF 트렌딩 1위 |
| 10-13 | Artificial Analysis Decision Index 공개. 결정 모델 중 Jev 1.13이 1위(58) |
| 10-14 | Jev 1.14. 이미지 입력(실험), Box 타입, 262k 롱컨텍스트(실험) |

### 5.2 채택과 현실

- **채택**: 창업자는 하루 1조 토큰을 넘었다고 말한다. Vercel 엔지니어는 LLM을 대체한 안전 분류기가 5–18배 빨라졌다고 보고했다. 연동은 Vercel, Netlify, LangChain(`TypeSafeClassifier`, tool call을 실행 전에 걸러내는 AutoMode middleware)이 있다.
- **과장 보정**: 공식 수치는 193.6배 빠르고 444.6배 싸다는 것이다. 출시 트윗 12,759건 분석에서 사용자 보고 중앙값은 **7배 빠르고 30배 싸며 지연 76ms**였다. 상한값이 아니라 중앙값으로 기대를 잡아야 한다.
- **비판**: 타입은 틀릴 수 없지만 **값은 틀릴 수 있다**. 확률 50%에서 행동할지 결정하는 부담이 사용자에게 넘어간다는 지적도 있다(Armin Ronacher). 숫자 세기, 산술, 날짜 비교, 크고 지저분한 state에 약하다고 TypeSafe 문서도 인정한다.

### 5.3 경쟁 지형

| 진영 | 대표 | 전략 |
|---|---|---|
| 원조 | TypeSafe Jev | 폐쇄 가중치, 범용 결정, 데이터와 보정에 집중 |
| 빅테크 API | OpenAI Decisions API | 기존 LLM 위에 결정 인터페이스를 얹음. 입력만 과금 |
| 빅테크 오픈 | Amazon Strands Decider 2B | 작은 오픈 모델로 AWS 에이전트 워크플로에 공급 |
| 오픈 증류 | AutoTrust JEV-27B/9B, JevK5 | 큰 모델(Jev 포함) 출력을 작은 모델로 증류 |
| 오픈 인코더 | Laya, Von, OpenDecider-nano | 로컬·저지연 |
| 수직 특화 | Security-One 27B, Dwight 4B(영업 통화), WebJev(브라우저) | 특정 도메인 데이터 |
| 학습 없음 | SemIf, LitJev | 기존 모델 로짓만 읽음 |

## 6. 왜 다른 기업이 이렇게 빨리 비슷하게 내는가

### 6.1 복제가 쉬운 이유

1. **인터페이스가 단순하고 공개돼 있다.** `POST /v1/systemone`에 state와 질문을 넣으면 확률이 나온다. 이 형태를 흉내 내는 서버는 하루면 만든다. 실제로 Ollama, llama.cpp, vLLM, SGLang이 같은 엔드포인트를 지원한다. 2차 분석들도 "오픈 클론은 모델이 아니라 인터페이스를 복제했다"고 정리한다.
2. **구조에 비밀이 적다.** `[MASK]` 점수, 로짓 읽기, prefix 재사용은 모두 공개된 기법이다. TypeSafe도 구조가 아니라 데이터가 해자라고 말한다.
3. **오픈 백본이 강하다.** Qwen3.5-4B에 LoRA만 붙여도 쓸 만하다. JEV-9B의 결정 블록은 백본의 0.5%(40.2M 파라미터)이고 B200 약 3 GPU-시간으로 학습했다. Amazon의 Marc Brooker는 작은 시장용 모델이면 수백–수천 달러로 만들 수 있다고 본다.
4. **확률 API는 증류 신호가 풍부하다.** 정답 하나가 아니라 선택지별 확률 분포(soft label)를 돌려주기 때문에 작은 모델이 따라 배우기 좋다. JEV-27B는 Jev 1.13을 증류했다고 밝힌다. TypeSafe 약관이 증류를 막는지는 확인하지 못했다.
5. **학습 없이도 상당히 따라간다.** SemIf는 동결된 4B 모델의 로짓만 읽는다. 참조 라벨과의 일치율이 SemIf 0.845, Jev 0.883이었다는 2차 보도가 있다.
6. **빅테크는 추가 비용이 거의 없다.** 이미 LLM 서빙과 prefix caching 인프라가 있다. 생성 단계를 빼고 확률만 읽는 엔드포인트 하나를 추가하면 된다. OpenAI가 14일 만에 낸 이유다.
7. **공개 벤치마크는 과적합하기 쉽다.** 좁은 과제에서 이겼다는 주장은 쉽게 나온다. 예를 들어 NanoJev는 게임 과제 4개에서 Jev를 이겼지만 같은 게임으로 학습하고 평가했다.

### 6.2 그래도 복제하기 어려운 것

| 어려운 것 | 근거 |
|---|---|
| 넓은 분포에서의 정확도 | Laya 제로샷 0.362(무작위 0.318). 파인튜닝한 과제 밖에서는 약하다 |
| 많은 선택지 | Banking77에서 Jev 0.870 vs Laya 0.425 |
| 보정 품질 | 오픈 모델은 대부분 과신한다. 런타임과 양자화가 바뀌면 보정을 다시 해야 한다 |
| 강건성 | 비슷한 입력에 비슷한 출력. 창업자가 결정론보다 중요하다고 강조하는 축이다 |
| 데이터 파이프라인 | 합성 데이터를 만들고, 사람이 실패를 찾고, 다시 만드는 루프. 창업자는 TypeSafe를 "데이터 랩"이라고 부른다 |

창업자의 평가도 같다. 클론들은 "멋진 아키텍처를 구현하고 싶은 ML 엔지니어 쪽에 가깝고", "모델을 실제로 똑똑하게 만드는 어려움을 과소평가한다"고 말한다. 동시에 2년 안에 비슷한 제품군이 산업으로 자리 잡을 것이라고 예상한다.

**정리**: 복제되는 것은 인터페이스와 구조다. 복제되기 어려운 것은 데이터, 보정, 강건성이다.

## 7. 앞으로의 전망

| 전망 | 근거 | 신뢰도 |
|---|---|---|
| 결정 엔드포인트가 모든 LLM 제공자의 기본 기능이 된다. 과금은 입력 토큰만 받는 방식이 표준이 된다 | OpenAI가 이미 같은 과금으로 출시. 서빙 인프라 재사용 비용이 낮음 | 높음 |
| 경쟁 축이 속도·가격에서 보정·강건성·버전 안정성으로 옮겨간다 | 가격은 이미 바닥 근처. 사용자 보고 중앙값 30배 절감. 창업자도 "nines of reliability"를 목표로 둠 | 높음 |
| 결정 모델이 캐스케이드의 첫 단계로 자리 잡는다. 확신이 낮으면 LLM이나 사람에게 넘긴다 | 창업자가 "보정된 모델의 캐스케이드"를 비용 절감 경로로 언급. LangChain middleware, stuntd 같은 도구 등장 | 높음 |
| "언제 되물을지", "언제 넘길지"를 모델이 직접 내놓는다 | LAVOIR(질문 가치 예측), Laya의 act/escalate head 시도. 아직 Laya head는 작동하지 않음 | 중간 |
| 멀티모달·Box·롱컨텍스트로 컴퓨터 사용과 브라우저 판단에 들어온다 | Jev 1.14 실험 기능, JEV-27B-VL, WebJev. 창업자는 컴퓨터 사용이 아직 안 풀렸다고 봄 | 중간 |
| 온디바이스 소형 결정 모델이 늘어난다 | Laya-CoreML/MLX/laya.cpp 포팅, Von CPU 15ms 미만. 개인정보와 지연 요구 | 중간 |
| 수직 특화 결정 모델이 범용 모델을 좁은 과제에서 이긴다 | Security-One, Dwight, NanoJev 사례. 다만 과적합 주의 | 중간 |
| state 안의 적대적 텍스트가 주요 보안 이슈가 된다 | JevAdvBench: 의견 한 줄로 Jev 1.13 결정의 12.1%가 뒤집힘 | 높음 |
| 증류를 둘러싼 약관·기술 방어가 생긴다 | 확률 API는 증류에 유리. 지금은 공개된 대응 없음 | 낮음 |

## 8. 차별화 전략: 결정 모델 사업자라면 무엇을 해자로 삼는가

시장 참여자 관점에서 차별화 지점을 정리한다. 우리에게 주는 시사점은 9장에서 다룬다.

1. **데이터 루프**: 합성 데이터 생성, 실패 사례 발굴, 재생성을 반복하는 파이프라인. 아키텍처는 복제되지만 이 루프와 누적 데이터는 복제되지 않는다.
2. **측정 가능한 보정**: "confidence 0.9면 실제로 90% 맞는다"를 보장 수준으로 공개한다. 확률을 돌려주는 제품에서 확률이 정직하다는 것은 핵심 가치다.
3. **강건성과 적대 내성**: 비슷한 입력에 같은 답, 주입된 문장에 흔들리지 않는 답. 앞으로 공격이 늘수록 가치가 커진다.
4. **버전 안정성**: 배포한 모델을 조용히 바꾸지 않고, LTS 버전과 폐기 사전 고지를 둔다. 엔터프라이즈는 이 약속에 돈을 낸다.
5. **도메인 데이터**: 범용 모델이 약한 좁은 영역(보안 분류, 영업 통화, 브라우저 화면)의 레이블 데이터.
6. **유통 채널**: Vercel Gateway, LangChain middleware처럼 개발자가 이미 쓰는 곳에 기본값으로 들어가기.
7. **자기 과제로 재는 도구**: 공개 벤치마크는 신뢰를 주지 못한다. 고객이 자기 데이터로 정확도와 보정을 측정하는 도구(jevcal류)가 신뢰를 만든다. 창업자도 공개 벤치마크보다 워크플로별 평가를 강조한다.

## 9. 우리가 쓸 수 있는 전략

### 9.1 기본 방향

우리는 Deep Agents와 LangGraph 기반 브라우저 에이전트(quick/deep 실행 프로파일)와 webmcp 워크플로를 만든다. 결정 모델을 직접 학습할 이유는 없다. Jev에서 가져올 것은 모델보다 **설계 원칙**이다.

1. **판단을 타입 있는 결정으로 분해한다.** 에이전트 안의 "LLM에게 물어보는 곳" 중 답이 닫혀 있는 곳을 찾아 `choice`/`score`/`noul`로 바꾼다.
2. **백엔드에 의존하지 않는 결정 포트를 만든다.** 시장이 빠르게 바뀌므로 Jev, OpenAI Decisions API, 로컬 Laya, 기존 LLM의 로짓 읽기 중 무엇이든 꽂을 수 있어야 한다. webmcp의 `providers/` 포트 구조와 같은 방식이다.
3. **confidence로 캐스케이드한다.** 높으면 바로 실행하고, 중간이면 LLM에 넘기고, 되돌릴 수 없는 행동이면 사람 승인을 받는다. 임계값은 행동별로 다르게 둔다.
4. **우리 해자는 도메인 평가셋이다.** 에이전트 실행 로그에서 결정 지점과 결과를 자동으로 모아 브라우저 판단 평가셋을 만든다. 백엔드가 바뀌어도 이 평가셋으로 바로 비교할 수 있다. 8장의 1번(데이터 루프)과 7번(자기 과제 평가)을 우리 규모로 하는 셈이다.

### 9.2 적용 후보

| 위치 | 결정 | 타입 | 넘길 곳 |
|---|---|---|---|
| 실행 시작 | 이 요청은 quick으로 충분한가 deep이 필요한가 | `choice` + confidence | 애매하면 deep |
| 매 스텝 화면 이해 | 이 화면은 로그인/검색결과/상품상세/오류 중 무엇인가 | `choice` | LLM 화면 분석 |
| 방해 요소 처리 | 이 모달·쿠키 배너를 닫아야 하나 | `noul` | LLM |
| 액션 전 게이트 | 이 클릭은 결제·삭제·전송처럼 되돌릴 수 없나 | `noul` | 사람 승인 |
| tool call 사전 검사 | 이 도구 호출은 사용자 의도와 맞나 | `noul` | LLM 재검토 |
| 완료 검증 | Todo가 실제로 완료됐나 (Aside식 완료 검증) | `noul` | LLM 검증 |
| webmcp 워크플로 | 이 스텝이 성공했나, self-heal이 필요한가 | `choice` | 재시도 또는 LLM |
| 요소 선택 | 후보 요소 중 어느 것이 목표인가 | `choice` (최대 255) | LLM. 인코더 계열은 선택지가 많으면 약함 |

9월 [DeepSeek Engram 보고서](../sep/deepseek-engram-browser-agent-idea-report.md)의 게이트와 L2 화면 메모리와도 이어진다. 화면 분류 결정을 메모리 키로 쓰고, 게이트를 결정 모델로 구현할 수 있다.

### 9.3 단계별 계획

1. **결정 포트 정의**: `decide(state, questions) -> typed answers + confidence` 인터페이스를 만든다. 첫 백엔드는 지금 쓰는 LLM을 structured output이나 로짓 읽기로 감싼다. 새 의존성 없이 시작할 수 있다.
2. **결정 지점 수집**: 기존 실행 로그에서 9.2의 판단 지점을 뽑아 (state, 질문, 실제 결과) 형태로 저장한다. 결과는 이후 스텝의 성공·실패로 자동 라벨링한다.
3. **오프라인 비교**: 같은 평가셋으로 백엔드별 정확도, ECE, 지연, 비용을 잰다. 로컬 후보는 Laya-multilingual(한국어 페이지 대응), OpenDecider-nano다.
4. **섀도 모드**: 실제 실행에서는 기존 LLM 판단을 쓰고, 결정 모델의 답과 confidence는 기록만 한다. 일치율과 임계값을 맞춘다.
5. **캐스케이드 적용**: 위험이 낮은 결정(화면 분류, 모달 처리)부터 결정 모델을 앞에 둔다. 되돌릴 수 없는 행동 게이트는 마지막에 적용하고, 단독으로 쓰지 않는다.
6. **필요하면 증류**: 평가셋이 쌓이고 비용 압박이 크면, GPU 환경에서 작은 모델을 우리 데이터로 파인튜닝한다.

### 9.4 리스크

| 리스크 | 대응 |
|---|---|
| 웹 페이지가 적대적이다. state 안의 문장이 결정을 뒤집을 수 있다(12.1%) | 되돌릴 수 없는 행동은 결정 모델 단독으로 허용하지 않는다. state는 신뢰할 수 없는 입력으로 다룬다 |
| 한국어 성능 | 영어 우선 모델이 많다. 다국어 체크포인트와 한국어 평가 문항을 따로 둔다 |
| 선택지가 많으면 약하다 | 요소 선택은 계층형 선택(영역 → 요소)으로 쪼개거나 LLM 계열 백엔드를 쓴다 |
| 확신을 갖고 틀린다 | confidence 임계값을 우리 평가셋으로 맞춘다. 보정은 런타임과 양자화별로 다시 한다 |
| 버전 변경으로 동작이 바뀐다 | 모델 ID를 고정하고, 버전을 올릴 때 평가셋을 다시 돌린다 |
| 시장이 너무 빨리 바뀐다 | 결정 포트로 백엔드를 추상화해 교체 비용을 낮춘다 |

## 10. 최종 판단 및 다음 액션

Jev가 바꾼 것은 모델 구조보다 **"작은 판단은 타입 있는 결정으로, 큰 판단은 LLM으로"라는 분업 방식**이다. 이 분업은 업계 표준이 될 가능성이 높고, 결정 모델 자체는 빠르게 범용재가 될 것이다. 우리에게 남는 차별점은 어떤 판단을 결정으로 뽑아낼지 아는 것, 그리고 그 판단을 잴 수 있는 우리 도메인 데이터다.

권장 다음 액션은 다음과 같다.

1. 현재 에이전트 그래프와 webmcp 워크플로에서 답이 닫혀 있는 LLM 호출 지점을 목록으로 만든다.
2. 결정 포트 인터페이스 초안을 쓰고, 기존 LLM 백엔드로 감싼 첫 구현을 만든다.
3. 실행 로그에서 결정 지점 100–300개를 뽑아 첫 평가셋을 만든다.
4. 로컬에서 Laya-multilingual과 OpenDecider-nano를 평가셋에 돌려 기준선을 잡는다.
5. 화면 분류와 모달 처리부터 섀도 모드로 붙인다.

## 참고 자료

창업자·공식
- [Latent Space 인터뷰: Jev, System One models for Prod, not God](https://www.latent.space/p/jev)
- [TypeSafe blog, Jev 1.14](https://typesafe.ai/blog/jev-1-14)
- [Laya HF 모델 카드](https://huggingface.co/convaiinnovations/laya)
- [LAVOIR 논문 (arXiv 2609.30706)](https://arxiv.org/abs/2609.30706)

보도·분석
- [InfoQ: TypeSafe AI Releases Jev](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/)
- [TechCrunch: Amazon releases its own Jev clone](https://techcrunch.com/2026/10/01/amazon-releases-its-own-jev-clone-as-decision-models-flood-the-web/)
- [System One Decision Models deep dive (local-ai-zone)](https://local-ai-zone.github.io/blog/system-one-decision-models-deep-dive.html)
- [System One model 용어 설명 (Sanity)](https://www.sanity.io/glossary/system-one-model)
- [Jev 원리 (Maxim)](https://www.getmaxim.ai/articles/what-is-jev-system-one-model/)
- [RLCD vs RLHF (MindStudio)](https://www.mindstudio.ai/blog/typesafe-jev-rlcd-vs-rlhf)
- [ExplainX Jev 1.14 팩트체크](https://explainx.ai/blog/jev-1-14-danger-zone-multimodal-box-long-context-claimed-vs-verified-2026)
- [Artificial Analysis Decision Index](https://artificialanalysis.ai/articles/artificial-analysis-decision-index)
- [awesome-decision-models](https://github.com/AnotiaWang/awesome-decision-models/wiki)

검색 결과로만 확인 (본문 미확인)
- [OpenAI Decisions API 공개 베타 (OpenAI 커뮤니티)](https://community.openai.com/t/decisions-api-is-now-available-in-public-beta/1403877)
- [OpenAI Decisions API vs Jev (Firecrawl)](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)
- [Jev 출시와 $40M (winzheng)](https://www.winzheng.com/en/article/typesafe-ai-jev-system-one-model-launch)
- [Laya 벤치마크 (Flowtivity)](https://flowtivity.ai/blog/laya-open-source-jev-alternative/)

# Jev와 Jev-like 결정 모델: 기본 구조와 업계 현황 보고서

## 1. 보고 개요

- 작성일: 2026-10-16
- 보고 목적: TypeSafe AI의 결정 모델 Jev(System One)와 오픈소스 Jev-like 모델의 동작 원리를 기초부터 정리하고, 2026-10 기준 업계 현황(비전 지원, 오픈 모델, 벤치마크)을 정리한다.
- 조사 방식: 이전 Claude 채팅 세션의 조사 노트를 바탕으로, 핵심 수치를 원문에서 다시 확인했다. 원문에서 확인한 항목과 2차 보도만 있는 항목을 구분해 표기한다.
- 문서 상태: 조사 단계. 코드 실행이나 직접 벤치마크는 하지 않았다.

## 2. 한 줄 결론

Jev류 결정 모델은 **답을 생성하지 않고, 요청 시 정의한 유한한 선택지 각각에 확률을 매기는 한 번의 forward pass 분류기**다. 지연(약 0.1초)과 비용이 LLM보다 한두 자릿수 작고 스키마 위반이 없다. 대신 설명·생성·연쇄 추론은 할 수 없어서 라우팅, 게이트, 분류 같은 빠른 판단층에 두고 어려운 판단은 LLM으로 넘기는 구성이 맞다. 오픈소스는 Laya 같은 인코더 계열과 Qwen 기반 LLM 백본 계열로 나뉘어 빠르게 늘고 있지만, 벤치마크마다 순위가 달라 자체 보고 수치는 그대로 믿기 어렵다.

## 3. Jev 기본 정보

| 항목 | 내용 | 확인 |
|---|---|---|
| 개발사 | TypeSafe AI, 창업자 Diogo Almeida | 원문 |
| 공개 | 2026-09-15, $40M 투자와 함께 공개 | 원문 (투자사 DCVC는 2차 보도만) |
| 접근 | 호스팅 API 전용 `POST /v1/systemone`, 가중치 비공개 | 원문 |
| 모델 ID | `jev-1.13.0` (안정판), `jev-1.14.0` (`jev-preview`) | 원문 |
| 가격 | 입력 100만 토큰당 $0.042, 출력 무료 | 원문 |
| 한도 | 요청당 64k 토큰, 상태+가장 긴 질문 32k. 250k 토큰/초, 1,200 요청/분 | 원문 |
| 지연 | 70–500ms. 질문 수가 늘어도 거의 일정하다고 주장 | 원문 (자체 보고) |
| SDK | Python `typesafe-sdk`, JS/TS `@typesafe-ai/sdk` | 원문 |

질문 타입은 세 가지다.

| 타입 | 의미 | 출력 |
|---|---|---|
| `choice` | 라벨이 붙은 선택지 중 하나 고르기 (최대 255개) | 선택지별 확률 + confidence |
| `score` | 자연어로 기술한 순서형 척도 위의 위치 | 단계 사이 값도 가능 + confidence |
| `noul` | yes/no 명제의 참 확률 | 0~1 확률 (별도 confidence 없음) |

## 4. 원리: 기존 LLM 디코딩과의 차이

### 4.1 Autoregressive 디코딩 vs 한 번의 pass

| 구분 | LLM (autoregressive) | Jev류 결정 모델 |
|---|---|---|
| 출력 방식 | 토큰을 하나씩 생성 | 선택지별 확률을 한 번에 계산 |
| forward pass 수 | 출력 토큰 수만큼 | 1회 |
| 지연 | 출력 길이에 비례 | 입력 길이에 주로 의존 |
| 출력 형식 | 자유 텍스트, 스키마 위반 가능 | 닫힌 답 공간, 타입 오류 없음 |
| 확률 | 선택한 답만 나옴 | 모든 선택지의 분포가 나옴 |

중요한 점은 **답 공간이 모델의 출력 어휘가 아니라 요청 시 사용자가 넣은 선택지**라는 것이다. 그래서 재학습 없이 새 스키마를 쓸 수 있다.

### 4.2 TypeSafe가 공개한 것과 공개하지 않은 것

- 공개: non-autoregressive, 한 번의 병렬 pass, 질문끼리 문맥을 공유하지 않고 독립적으로 평가, RLCD로 사후 학습
- 비공개: 아키텍처, 손실함수, 학습 데이터 구성. "parallel sampler", "합성 데이터"는 2차 글에만 나오고 원문에서 확인하지 못했다.
- 따라서 아래 5장의 구조는 **오픈 모델 Laya에서 확인한 것**이고, Jev 내부가 같다는 보장은 없다.

### 4.3 RLCD (Reinforcement Learning for Calibrated Decisions)

- RLHF: 사람 평가자가 선호하는 답을 강화한다. "그럴듯하게 들리는 것"을 최적화한다.
- RLCD: 결정과 함께 내놓은 확률이 실제 정답 빈도와 맞도록 강화한다. "맞는 것과 얼마나 확신하는지"를 최적화한다.
- Laya가 공개한 RLCD 구현은 **strictly proper scoring rule**(log, spherical, 순서형은 RPS)을 보상으로 쓴다. proper scoring rule은 자기가 믿는 확률을 정직하게 보고할 때 기대 보상이 최대가 되는 규칙이라, 확률 보정(calibration)이 학습 목표에 직접 들어간다.

## 5. 한 번의 pass로 가변 선택지를 처리하는 법 (Laya 기준)

### 5.1 먼저 알아야 할 것: BERT와 `[MASK]`

- **GPT**는 decoder다. 각 토큰이 자기 왼쪽만 보고 다음 토큰을 예측한다. 생성용이다.
- **BERT**는 encoder다. 모든 토큰이 양방향으로 서로를 본다. 생성하지 않고, 입력 토큰마다 문맥이 반영된 벡터를 한 번에 출력한다. 이해·분류용이다.
- 특수 토큰은 세 가지다.
  - `[CLS]`: 맨 앞에 붙는다. 문장 전체 요약 벡터로 쓴다.
  - `[SEP]`: 구간 구분자다.
  - `[MASK]`: 가려진 빈칸이다.
- BERT는 사전학습 때 일부 토큰을 `[MASK]`로 가리고 원래 토큰을 맞힌다. 그래서 `[MASK]` 위치의 벡터는 **주변 문맥 전체를 보고 "여기에 무엇이 와야 하는가"를 요약하도록** 학습돼 있다.
- **ModernBERT**는 Answer.AI와 LightOn이 만든 현대화 BERT다(긴 문맥, 빠른 attention). Laya는 ModernBERT-large(395M)를 백본으로 쓴다.

### 5.2 Laya의 처리 순서

```text
[CLS] <type> question [SEP] [MASK] option1 [MASK] option2 [MASK] option3 [SEP] state [SEP]
```

1. 선택지를 출력 어휘가 아니라 **입력**에 넣고, 각 선택지 앞에 `[MASK]` 마커를 붙인다.
2. 양방향 인코더를 한 번 통과시킨다. 각 `[MASK]` 벡터는 질문, 자기 선택지, 다른 선택지, state를 모두 본 상태가 된다.
3. 각 `[MASK]` 위치 벡터를 decision head(2층 트랜스포머 + 질문 타입 임베딩 + 선택지 scorer)에 넣어 마커마다 점수(스칼라) 하나를 얻는다.
4. 그 질문의 마커 점수끼리만 softmax해 K-way 확률을 만든다. K가 3이든 20이든 마커 수만큼만 softmax하면 된다.
5. `choice`/`score`/`noul`은 같은 마커 벡터를 어떻게 읽느냐의 차이다.

`[MASK]`를 선택지 자리표시로 쓰는 이유는 문서에 명시돼 있지 않다. "사전학습에서 문맥 전체를 요약하도록 훈련된 위치라 선택지 점수를 뽑기 좋다"는 것은 해석이다.

### 5.3 여러 질문 처리

- Laya는 **질문 하나당 시퀀스 하나**를 만들고, 한 호출의 여러 질문은 배치로 묶어 한 번의 forward pass로 돌린다.
- state는 질문마다 반복 입력되므로 질문이 늘면 지연도 는다. T4 기준 `laya`는 질문 1개 39.5ms, 10개 158.6ms, 50개 771ms다.
- "state를 한 번만 읽고 질문 수와 무관하게 지연이 일정하다"는 TypeSafe의 Jev 설명이고, Laya 구조와는 다르다.

## 6. Laya 상세 (오픈소스 대표 모델)

| 항목 | 내용 |
|---|---|
| 개발 | Convai Innovations, Apache-2.0, HF `convaiinnovations/laya`, PyPI `laya` |
| 구조 | ModernBERT-large 395M + decision head = 421M. 다국어 변종 322M (mmBERT-base, 100+ 언어) |
| 학습 | RLCD: 로짓에 가우시안 노이즈로 탐색, proper scoring rule 보상, group-mean baseline REINFORCE (GRPO 방식) |
| 호환 | `laya-serve`가 Jev와 같은 `/v1/systemone` 형태 제공 |

체크포인트는 세 가지다.

| 체크포인트 | 백본 | 파라미터 | 문맥 | 용도 |
|---|---|---|---|---|
| `laya` | ModernBERT-large | 421M | 512 | 영어 텍스트, 가드레일, 이메일 분류 |
| `laya-multilingual` | mmBERT-base | 322M | 1024 (최대 8k) | 100+ 언어 |
| `laya-typed-decisions` | ModernBERT-large | 421M | 1024 | typed-decisions 워크플로 파인튜닝 |

모델 카드가 밝힌 한계는 다음과 같다.

| 한계 | 수치 |
|---|---|
| 제로샷 정확도가 무작위 수준 | `laya` 0.362, 무작위 0.318, 다수 클래스 0.461. 파인튜닝 체크포인트는 0.766 |
| 과신(over-confidence) | (질문 타입, 선택지 수)별 온도 재보정으로 평균 ECE 0.466 → 0.081 |
| 선택지가 많으면 약함 | Banking77에서 Jev 0.870 vs Laya 0.425. 고정 토큰 예산 때문에 라벨당 3–4토큰만 남음 |
| `score`가 가장 약함 | SST-5 0.372 |
| `noul` 라벨 편향 | state보다 `false:`/`true:` 라벨을 따라갈 수 있음. 2지선다 `choice`로 바꾸기 권장 |
| act/escalate head 미작동 | `act_probability`가 거의 항상 1.0 (AUROC 0.30). 대신 `confidence`로 게이트 (AUROC 0.77) |

정리하면 Laya는 **구조를 공부하고 로컬에서 실험하기 좋은 모델**이지만, 제로샷으로 바로 쓰기는 어렵고 자기 데이터로 파인튜닝과 온도 보정을 해야 한다.

## 7. 비전 지원 현황

### 7.1 공식 Jev 1.14 (2026-10-14 발표)

| 항목 | 내용 | 확인 |
|---|---|---|
| 이미지 입력 | 헤더 `TypeSafe-Danger-Zone-Images: true`. `assets` 맵으로 이미지를 넣고 `state`/`instructions`/`criteria`에서 참조 | 원문 |
| 1.13 지원 | TypeSafe는 1.13이 "원래 멀티모달이었다"고 주장 | 원문 (주장) |
| Box 타입 | 바운딩 박스 하나를 반환. 1.14 전용 | 원문. 정확도 수치 없음 |
| 롱컨텍스트 | 헤더 `TypeSafe-Danger-Zone-Long-Context: true`. 64k/32k 기본 한도를 262k로 확장 (1.13, 1.14 모두) | 262k는 문서 기준 팩트체크 글 |
| 경고 | 프로덕션용 아님, 이미지는 텍스트보다 성능 낮음, 롱컨텍스트는 느리고 덜 정확 | 원문 |
| 별칭 | `jev-latest`는 약 일주일 뒤 1.14로 전환 예정. 1.13 폐기 60일 전, 1.14 폐기 30일 전 고지 | 원문 (계획) |
| 개선 | 전반적 소폭 개선, 다국어 개선이 가장 클 것으로 기대. 자체 벤치 60.0 vs 58.9 | 자체 보고 |

TypeSafe 모델 문서는 아직 입력을 text only로 표기하고 있다. 이미지 기능은 실험 단계로 보는 게 맞다.

### 7.2 오픈 모델

| 모델 | 내용 |
|---|---|
| AutoTrust JEV-27B-VL (10/8) | HF 트렌딩 1위. Jev Decision Index 비전 보드 69.82. 결정 adapter와 head는 텍스트로만 학습했고 비전 경로는 Qwen 베이스 그대로라 **이미지 판단은 전부 zero-shot** |
| AutoTrust JEV-9B | 결정 블록 40.2M 파라미터(백본의 약 0.5%), B200 약 3 GPU-시간으로 학습. 10/3 비전 업데이트는 2차 보도만 확인 |
| Vev | Qwen 4B/9B, 비전 입력. 가중치는 비상업 라이선스 |
| 기타 | pplx-decider-v1.1-27b, Standard One, Intern-Decision, OneJev, Valen 등이 멀티모달 지원 |

## 8. 오픈소스 Jev-like 지형

### 8.1 인코더 계열 (작고 로컬)

- 구조: BERT류 인코더 + 선택지 마커 점수. 수백 M 파라미터라 CPU나 작은 GPU에서 돈다.
- 대표: Laya와 파생(OpenJevX, Laya MoE, 게임용 LoRA), OpenDecider-nano(Ettin 인코더), GLiNER2.5-Decide(DeBERTa-v3-large), Phocinae-Largha-150M(영/중)
- 포팅: Laya-MLX, Laya-CoreML, laya.cpp, sys1(Rust/candle)

### 8.2 LLM 백본 계열 (더 크고 비전 지원)

- 구조: Qwen 등 디코더 LLM에 LoRA나 작은 decision head를 붙인다. 선택지 문자(A/B/C)의 다음 토큰 확률을 읽거나 선택지별 log-likelihood를 계산해 한 번의 pass로 분포를 얻는다.
- 대표: AutoTrust JEV-27B/9B(Jev 1.13 증류), OpenDecider-small(Qwen3-4B + LoRA), JevK5, Clef, Decision 2.0, WebJev(브라우저 에이전트용 35B-A3B), Jeeves(결정 전에 추론하는 9B)
- 학습 없는 방식: SemIf, LitJev, simple-jev 등이 기존 LLM을 그대로 결정 모델처럼 쓴다.

### 8.3 서빙과 도구

- `/v1/systemone` 호환 서버: Ollama, llama.cpp `llama-server`(이미지 입력 포함), SGLang, vLLM Jev, openjev, Ollaya, stuntd(Laya + 신뢰도 임계값 + 폴백)
- 보정 도구: jevcal(질문별 confidence 임계값 적합)
- 라이선스 주의: OpenJev, StartLux 가중치는 CC BY-NC 4.0, Vev는 비상업. 이름이 비슷한 별개 프로젝트가 많다(OpenJev 가중치 vs openjev 서버 등).
- 보안 주의: 일부 로컬 런타임은 모델 repo에 포함된 코드를 사용자 권한으로 실행할 수 있다. 쓰기 전에 코드를 확인한다.

## 9. 벤치마크: 순위가 엇갈린다

| 벤치마크 | 결과 | 성격 |
|---|---|---|
| Artificial Analysis Decision Index v1.0 (10/13) | Claude Haiku 5.5 (Low) 61 (1.4초), **Jev 1.13 58 (0.13초, 결정 모델 1위)**, GLiDE 54, Microsoft-Decision-1 54. 가장 빠른 건 Celeris-1 Decision 0.06초 | 제3자, 4개 평가 가중 평균 |
| JevBench v1.4.2.2 | Imajev-4B 67.37, Plumb-4B 65.84, decider-4b v2 64.13, **Jev 1.13 63.29 (4위)** | 제3자, 정확도·보정·속도·비용 종합 |
| Jev Decision Index v0.3.1 | 절반을 비공개 벤치로 바꾼 뒤 d3가 1위. 수치 미공개 | 제3자, 독립 재현 필요 |
| OpenDecider 자체 비교 | 일반 결정 200문항: OpenDecider-small 0.735, Jev 0.730, Laya 0.570. Laya 배터리: Jev 0.774, Laya·OpenDecider 0.702 | 자체 보고, ±3점 오차, 단일 시드 |
| AutoTrust 자체 비교 | GEV-26B-Decide 적응 모드 83.4% (System 2를 47.8%에만 호출) vs 매번 추론 83.8% | 자체 보고 |

- 같은 Jev 1.13이 AA에서는 결정 모델 1위, JevBench에서는 4위다. 평가 과제와 점수 공식이 다르기 때문이다.
- JevBench는 버전마다 점수 공식이 바뀌어서(v1.2에서 Jev 74.4) 버전 간 비교가 안 된다.
- 인계 노트에 있던 "JEV-27B 84.07 vs Jev 83.85"는 AutoTrust 보도자료에서 찾지 못했다. benchlm 집계(Perplexity Decider 62.8, Jev 60.1, JEV-9B 45.2)와 Liquid AI d1 보도도 원문을 확인하지 못했다.

## 10. 공통 한계와 사용 패턴

### 한계

- 텍스트 생성과 설명이 안 되고, 답 공간을 미리 정의해야 한다.
- 부정·범위 해석, 개수 세기, 날짜 비교, multi-hop 추론, 크고 지저분한 state에 약하다.
- 형식 오류는 없지만 **확신을 갖고 틀릴 수 있다**. 형식 제약이 정답을 보장하지 않는다.
- state에 섞인 적대적 문장이 답을 바꿀 수 있다. JevAdvBench는 의견 한 줄을 덧붙여 Jev 1.13 결정의 12.1%가 뒤집혔다고 보고했다. state는 신뢰할 수 없는 입력으로 다룬다.

### 권장 패턴

- **캐스케이드**: Jev류로 대량·단순 판단을 처리하고, confidence가 낮으면 LLM이나 사람에게 넘긴다. 임계값은 행동별로 다르게 둔다(예: 되돌릴 수 없는 송금은 0.9).
- **분해**: 복합 판단은 단순 질문 여러 개로 쪼개고 점수 조합은 코드에서 한다.
- **버전 고정**: `jev-latest` 같은 별칭은 코드 변경 없이 답이 바뀔 수 있으니 `jev-1.13.0`처럼 버전을 고정한다.
- **자체 보정**: 오픈 모델은 자기 데이터로 온도나 임계값을 다시 맞춘다.

## 11. 브라우저 에이전트 관점의 시사점

- 에이전트 스텝 중 상당수는 "이 모달을 닫아야 하나", "이 페이지가 로그인 폼인가", "이 요소가 제출 버튼인가" 같은 닫힌 판단이다. 이런 판단을 결정 모델로 넘기면 LLM 호출과 지연을 줄일 수 있다.
- 9월 [DeepSeek Engram 보고서](../sep/deepseek-engram-browser-agent-idea-report.md)의 게이트(조회 결과 검증)와 캐스케이드(소형 모델 우선) 자리에 결정 모델을 넣을 수 있다.
- WebJev, OpenJev(브라우저 에이전트 teacher 궤적 증류), PlayJev처럼 브라우저 특화 모델이 이미 나오고 있다.
- 단, 웹 페이지 내용은 적대적일 수 있어 12.1% 뒤집힘 결과를 고려하면 되돌릴 수 없는 행동의 게이트로 단독 사용하면 안 된다.

## 12. 최종 판단 및 다음 액션

결정 모델은 "LLM을 더 빠르게 하는 것"이 아니라 **닫힌 판단을 확률 분포로 바꾸는 별도 계층**이다. 구조 학습은 Laya로, 품질 기준선은 Jev API로 잡는 것이 현실적이다. 벤치마크 순위보다 자기 과제에서 정확도와 보정을 직접 재는 것이 중요하다.

권장 다음 액션은 다음과 같다.

1. Laya를 로컬에서 실행해 고객 문의 분류 예시로 `[MASK]`별 점수와 softmax 확률을 숫자로 확인한다.
2. Laya 코드에서 decision head와 act/escalate head 구조를 직접 확인한다.
3. 브라우저 에이전트 실행 로그에서 닫힌 판단 스텝을 뽑아 Jev, Laya, OpenDecider로 정확도·ECE·지연을 비교한다.
4. TypeSafe Images 문서로 Jev 1.14 이미지 요청 형식을 정리하고, 스크린샷 판단에서 JEV-27B-VL과 비교한다.
5. 미확인 항목(d1, d3, GLiDE 사양, JEV-27B 84.07 수치)은 원문이 나오면 갱신한다.

## 참고 자료

원문 확인
- [TypeSafe blog, Jev 1.14](https://typesafe.ai/blog/jev-1-14)
- [Laya HF 모델 카드](https://huggingface.co/convaiinnovations/laya)
- [Jev 개요 (EveryDev)](https://www.everydev.ai/tools/jev/llms.txt)
- [Jev 원리 (Maxim)](https://www.getmaxim.ai/articles/what-is-jev-system-one-model/)
- [RLCD vs RLHF (MindStudio)](https://www.mindstudio.ai/blog/typesafe-jev-rlcd-vs-rlhf)
- [ExplainX Jev 1.14 팩트체크](https://explainx.ai/blog/jev-1-14-danger-zone-multimodal-box-long-context-claimed-vs-verified-2026)
- [Artificial Analysis Decision Index](https://artificialanalysis.ai/articles/artificial-analysis-decision-index)
- [JevBench](https://github.com/fstandhartinger/jevbench)
- [AutoTrust JEV-27B-VL (PR Newswire)](https://www.prnewswire.com/news-releases/autotrust-ais-jev-27b-vl-tops-hugging-face-global-trending-list-as-open-decision-models-gain-momentum-302902279.html)
- [OpenDecider (HF blog)](https://huggingface.co/blog/manjunathshiva/opendecider-beats-laya-and-jev)
- [awesome-decision-models](https://github.com/AnotiaWang/awesome-decision-models/wiki)
- [Jev Decision Index v0.3 / d3 (daily.dev)](https://daily.dev/posts/jev-decision-index-v0-3-adds-a-private-benchmark-half-d3-reaches-1-on-v0-3-1-spli94ufq)

이전 세션 노트에만 있고 이번에 열지 못한 자료
- [MarkTechPost, Jev 1.14](https://www.marktechpost.com/2026/10/14/typesafe-ai-jev-1-14-images-box-long-context/) (403)
- [AutoTrust JEV-9B (TechJack)](https://techjacksolutions.com/ai-brief/autotrust-jev-9b-vision-language-model-hugging-face/) (403)
- [GIGAZINE, Jev 1.14](https://gigazine.net/gsc_news/en/20261015-jev-1-14/)
- [1023 Jack 이미지 테스트](https://1023jack.com/news/jev-can-see-now-i-pointed-it-at-30-of-my-own-images/)
- [System One 설명 (Sanity)](https://www.sanity.io/glossary/system-one-model)
- [LAVOIR 논문](https://arxiv.org/pdf/2609.30706)
- [Laya 설명 (Medium, visrow)](https://medium.com/@visrow/what-is-laya-laya-vs-jev-with-live-demo-42c2ab494e02)
- [OpenJevX](https://huggingface.co/muthuishere/openjevx), [openJev-verdict-2.0](https://github.com/Heman10x-NGU/openJev-verdict-2.0/wiki), [Open Alternative to Jev](https://github.com/ikermoel/open-alternative-jev/wiki), [OpenJev](https://github.com/alanhuangyoo/OpenJev)
- [jev-compatible-server](https://pypi.org/project/jev-compatible-server/), [ollajev](https://pypi.org/project/ollajev/)

# Stanford CS224R Deep Reinforcement Learning 1~6강 정리 및 브라우저 에이전트 관점 보고서

- 작성일: 2026-08-28
- 저장소: `minguk-jang/spica_at_home`
- 대상 강의: Stanford CS224R Deep Reinforcement Learning, Spring 2025 Lectures 1~6
- 문서 상태: 강의 내용 및 핵심 관점 정리

## 1. 보고서 요약

Stanford CS224R Spring 2025의 1~6강은 다음 순서로 진행된다.

```text
MDP 문제 정의
  → 전문가 시연 학습
  → 정책 직접 개선
  → 가치함수로 개선 신호 안정화
  → 과거 데이터 재사용
  → 정책 없이 Q-function으로 행동 선택
```

강의의 핵심은 PPO, SAC, DQN 중 하나를 브라우저 에이전트에 바로 적용하는 것이 아니다. 더 중요한 내용은 에이전트를 다음과 같은 순차적 의사결정 시스템으로 이해하는 것이다.

```text
상태 관찰 → 행동 선택 → 환경 변화 → 새로운 상태 관찰 → 다음 행동 선택
```

이 관점에서 브라우저 에이전트의 동작과 실패를 분석하는 핵심 개념은 세 가지다.

1. 행동이 이후 상태와 데이터 분포를 바꾸는 폐루프 시스템
2. 긴 작업에서 각 행동의 성공 기여도를 판단하는 credit assignment
3. 전문가, 현재 정책, 과거 정책의 데이터를 구분해야 하는 distribution shift와 학습 안정성

## 2. 강의별 내용 정리

### 2.1 1강: Course Introduction + MDPs

#### 문제 정의

RL에서는 다음 요소로 경험을 표현한다.

- 상태 `s`: 세계의 상태
- 관측 `o`: 에이전트가 볼 수 있는 정보
- 행동 `a`: 에이전트가 수행하는 결정
- 보상 `r(s, a)`: 상태와 행동의 가치
- trajectory `τ`: 상태와 행동의 연속
- 정책 `πθ(a|s)`: 상태를 행동으로 변환하는 확률적 모델
- 환경 동역학 `p(s_{t+1}|s_t,a_t)`: 행동 이후 상태 변화

정책이 만들어내는 trajectory의 기대 누적 보상을 최대화하는 것이 RL의 기본 목표다.

```text
J(θ) = Eτ~pθ(τ) [ Σt r(st, at) ]
```

정책은 단순히 정답 행동을 예측하는 모델이 아니다. 정책의 행동이 환경을 바꾸고, 그 결과가 이후 정책 입력이 된다. 이 때문에 RL의 데이터는 일반적인 지도학습처럼 독립적이지 않다.

#### 가치함수

- `Vπ(s)`: 상태 `s`에서 정책 `π`를 따를 때의 기대 미래 보상
- `Qπ(s,a)`: 상태 `s`에서 행동 `a`를 수행한 뒤 정책 `π`를 따를 때의 기대 보상

이 두 함수는 이후 Actor-Critic과 Q-learning에서 학습 신호를 구성하는 기반이 된다.

#### 핵심 takeaway

1강은 RL을 단발성 행동 예측 문제가 아니라, 행동과 환경 변화가 연결된 최적화 문제로 정의한다.

### 2.2 2강: Imitation Learning

#### Behavior Cloning

Imitation Learning은 전문가가 수행한 trajectory를 이용해 정책을 학습한다.

```text
D = {(s, a)}
minθ - E(s,a)~D [ log πθ(a|s) ]
```

결정론적 정책에서는 전문가 행동을 MSE로 회귀할 수 있다. 하지만 여러 행동이 모두 가능한 상태에서는 평균 행동이 실제로 유효하지 않을 수 있다.

예를 들어 같은 목표를 달성하는 여러 클릭 경로가 있는데 전문가들이 서로 다른 버튼을 선택했다면, 단순한 평균 회귀는 어느 버튼도 정확히 선택하지 못하는 행동을 만들 수 있다.

#### Expressive policy

이 문제를 다루기 위해 행동을 하나의 평균값이 아니라 확률분포로 표현한다.

- Categorical distribution
- Mixture of Gaussians
- Autoregressive policy
- Diffusion policy

여기서 중요한 구분은 신경망의 크기와 행동분포의 표현력이 다르다는 점이다. 큰 신경망을 사용하더라도 출력 분포가 단일 Gaussian이면 다중 모드 행동을 충분히 표현하지 못할 수 있다.

#### Compounding error와 covariate shift

전문가 데이터로 학습한 정책은 전문가가 방문한 상태에 대해서는 잘 동작할 수 있다. 그러나 실제 실행 중 작은 오류가 발생하면 학습 데이터에 없던 상태로 이동할 수 있다.

```text
작은 행동 오류
  → 전문가 데이터에 없는 상태 방문
  → 더 큰 행동 오류
  → 오류 누적
```

이것이 compounding error이며, 전문가 상태 분포와 학습 정책의 상태 분포가 달라지는 현상을 covariate shift라고 한다.

#### DAgger

DAgger는 정책을 직접 실행하면서 정책이 방문한 상태에서 전문가 교정 행동을 수집한다.

1. 학습 정책 실행
2. 정책이 방문한 상태에서 전문가 행동 질의
3. 교정 데이터를 기존 dataset에 추가
4. 정책 재학습

Human-Gated DAgger에서는 에이전트가 계속 행동하되, 전문가가 오류가 발생하는 시점에 개입해 이후 행동을 교정한다.

#### 핵심 takeaway

2강의 핵심은 정상적인 전문가 행동을 복사하는 것만으로는 부족하다는 것이다. 에이전트가 실제로 만들어내는 오류 상태와 복구 행동도 학습 대상이 되어야 한다.

### 2.3 3강: Policy Gradients

#### 기본 아이디어

Policy Gradient는 정책을 직접 보상 방향으로 업데이트한다.

```text
높은 보상을 얻은 행동의 확률 증가
낮은 보상을 얻은 행동의 확률 감소
```

REINFORCE의 핵심 형태는 다음과 같다.

```text
∇θ J(θ)
≈ E [ Σt ∇θ log πθ(at|st) · Rt ]
```

`Rt`는 시점 `t` 이후의 reward-to-go다.

#### Causality

시점 `t`의 행동은 그 이전에 이미 발생한 보상에 영향을 줄 수 없다. 따라서 trajectory 전체 보상 대신 현재 행동 이후의 미래 보상만 사용하는 것이 더 효율적이다.

#### Baseline

보상에서 평균 보상이나 가치함수를 빼면 기대 gradient는 유지하면서 variance를 줄일 수 있다.

```text
∇θ log πθ(a|s) · (Rt - b)
```

이 방법은 어떤 행동이 평균보다 좋았는지를 중심으로 정책을 업데이트하게 한다.

#### 한계

Policy Gradient는 trial-and-error를 직접 표현하지만 다음 문제가 있다.

- gradient variance가 큼
- sparse reward에서 비효율적
- 많은 trajectory가 필요함
- 현재 정책이 만든 데이터를 계속 새로 수집해야 함

#### Off-policy 확장

과거 정책의 데이터를 재사용하기 위해 importance sampling을 사용할 수 있다. 하지만 trajectory가 길어지면 정책 확률비가 매우 커지거나 작아져 불안정해진다. 정책 간 차이를 KL divergence로 제한하는 방식도 소개된다.

#### 핵심 takeaway

3강은 정책이 성공한 행동을 더 자주 하도록 직접 업데이트할 수 있다는 점을 보여준다. 동시에 긴 trajectory와 희소한 보상에서는 어떤 행동이 실제로 기여했는지 판단하기 어렵다는 문제를 드러낸다.

### 2.4 4강: Actor-Critic Methods

#### Actor와 Critic

Actor-Critic은 Policy Gradient의 불안정성을 줄이기 위해 가치함수를 함께 학습한다.

- Actor: 정책 `πθ(a|s)`를 학습
- Critic: `V`, `Q`, `Advantage`를 추정

Advantage는 다음과 같다.

```text
Aπ(s,a) = Qπ(s,a) - Vπ(s)
```

즉, 특정 행동이 해당 상태에서 평균적인 행동보다 얼마나 좋은지를 나타낸다.

정책 gradient는 다음처럼 표현할 수 있다.

```text
∇θ J(θ)
≈ Σt ∇θ log πθ(at|st) · Â(st,at)
```

#### Critic 학습 방법

1. **Monte Carlo**
   - 실제 trajectory의 미래 보상 합을 target으로 사용
   - 편향은 작지만 variance가 큼

2. **TD bootstrapping**
   - `r + γV(s')`를 target으로 사용
   - 데이터 효율성이 높지만 현재 가치 추정에 의존함

3. **N-step return**
   - 여러 단계의 실제 보상과 이후 가치 추정을 결합
   - Monte Carlo와 TD 사이의 절충

#### 핵심 takeaway

Policy Gradient가 trajectory의 최종 결과를 이용한다면, Actor-Critic은 critic을 통해 각 상태와 행동의 가치를 추정한다. 따라서 “성공했는가”에서 한 단계 나아가 “현재 상태에서 어떤 행동이 평균보다 나았는가”를 학습할 수 있다.

### 2.5 5강: Off-Policy Actor-Critic

#### PPO

하나의 데이터 batch로 정책을 여러 번 업데이트하면 새 정책이 데이터를 생성한 이전 정책과 달라진다. PPO는 importance ratio를 사용하고 이를 clipping한다.

```text
r(θ) = πθ(a|s) / πold(a|s)
```

이를 통해 정책이 한 번의 update에서 지나치게 크게 변하는 것을 제한한다.

PPO의 핵심은 다음과 같다.

- 최근 batch를 여러 번 사용
- 정책 변화 폭을 제한
- clipping으로 불안정한 update 방지
- 안정성과 사용 편의성이 비교적 높음

#### Replay Buffer와 SAC

더 과거의 데이터를 재사용하려면 replay buffer를 사용한다. 이 경우 `V(s)`보다 `Q(s,a)`를 학습하면 transition `(s,a,r,s')`를 사용해 Bellman target을 만들기 쉽다.

SAC는 다음 요소를 결합한다.

- replay buffer
- Q-function
- stochastic policy
- entropy regularization
- reparameterization trick

SAC는 데이터 효율성이 높지만 PPO보다 하이퍼파라미터 조정이 어렵고 불안정할 수 있다.

#### 핵심 takeaway

5강은 데이터 재사용이 항상 공짜가 아니라는 점을 설명한다. 과거 데이터를 많이 사용할수록 샘플 효율성은 좋아지지만, 현재 정책과 과거 데이터를 생성한 정책의 차이를 관리해야 한다.

### 2.6 6강: Q-learning

#### 정책 없이 행동 선택

Q-learning은 정책을 별도로 학습하지 않고 Q-function만 학습한다.

```text
π(s) = argmaxa Q(s,a)
```

최적 Q-function은 Bellman optimality equation을 따른다.

```text
Q*(s,a)
= r + γ E[ maxa' Q*(s',a') ]
```

실제 학습에서는 다음 target을 사용한다.

```text
y = r + γ maxa' Qtarget(s',a')
```

#### 안정화 기법

- **Target Network**: target 계산용 네트워크를 느리게 업데이트
- **Double Q-learning**: 행동 선택과 행동 평가를 분리해 Q값 과대평가 감소
- **N-step Return**: 여러 단계의 보상을 사용해 초기 학습 속도 향상

Q-learning은 Actor가 없어도 된다는 장점이 있지만, 행동 공간이 크거나 연속적이면 `argmax`가 어렵고 Q-function을 정확하게 추정하기도 어렵다.

#### 알고리즘 선택 관점

- PPO: 안정성과 구현 편의성이 중요할 때
- DQN: 이산 행동 공간에서
- SAC: 데이터 효율성이 중요하고 튜닝 비용을 감수할 때

#### 핵심 takeaway

6강은 policy-based 방법과 value-based 방법의 차이를 정리한다. Q-learning은 정책을 직접 수정하는 대신, 각 행동의 장기 가치를 학습해 가장 높은 행동을 선택한다.

## 3. 1~6강을 관통하는 구조

각 강의는 독립적인 알고리즘 목록이 아니라 하나의 발전 과정으로 볼 수 있다.

```text
1. MDP
   문제를 상태, 행동, 보상, 전이로 정의

2. Imitation Learning
   전문가 행동을 보고 초기 정책 학습

3. Policy Gradient
   정책을 실행하고 보상으로 직접 개선

4. Actor-Critic
   가치함수로 행동의 상대적 기여도를 추정

5. PPO / SAC
   데이터를 여러 번 또는 과거까지 재사용

6. Q-learning
   정책 없이 Q-function만 학습하고 greedy action 선택
```

이 발전 과정은 세 가지 축으로도 정리할 수 있다.

| 축 | 변화 |
|---|---|
| 데이터 | 전문가 시연 → 현재 정책 데이터 → 과거 데이터 재사용 |
| 학습 대상 | 정책 → 정책과 가치함수 → Q-function |
| 신뢰성 문제 | 행동 모방 오류 → gradient variance → distribution shift와 update 불안정성 |

## 4. 브라우저 조작 에이전트에 대한 세 가지 핵심 관점

### 4.1 폐루프 시스템과 compounding error

브라우저 에이전트의 행동은 단순한 출력이 아니라 다음 입력을 만들어낸다.

```text
페이지 관찰
→ 클릭, 입력, 스크롤, 탭 전환
→ DOM, URL, 세션, 팝업 상태 변화
→ 변화한 페이지 재관찰
```

잘못된 클릭은 현재 행동 하나의 오류로 끝나지 않는다. 잘못된 페이지, 잘못된 탭, 로그인 모달, 다른 검색 결과를 만들고 이후 모든 행동의 전제가 달라질 수 있다.

따라서 브라우저 에이전트를 평가할 때는 첫 행동의 정확도만으로 충분하지 않다.

- 행동 이후 상태 변화를 제대로 인식하는가?
- 오류 이후 복구할 수 있는가?
- 새로운 DOM이나 팝업이 나타났을 때 대응하는가?
- 자기 행동이 만든 상태를 다음 행동의 근거로 사용하는가?

이 관점은 실패를 단순히 “LLM이 잘못된 답을 냈다”라고 보지 않고, 어느 행동이 이후 상태 분포를 망가뜨렸는지 분석하게 한다.

### 4.2 Credit assignment와 장기 작업

브라우저 작업에서는 최종 성공 여부가 마지막에야 확인되는 경우가 많다.

```text
검색
→ 결과 선택
→ 상세 페이지 진입
→ 옵션 설정
→ 장바구니
→ 결제 완료
```

최종 실패만으로는 검색어가 문제였는지, 상품 선택이 문제였는지, 옵션 설정이 문제였는지 알기 어렵다.

가치함수 관점은 이 문제를 분해한다.

- `V(s)`: 현재 상태가 얼마나 성공에 가까운가?
- `Q(s,a)`: 현재 상태에서 특정 행동을 했을 때 성공 가능성은 얼마나 되는가?
- `A(s,a)`: 평균적인 행동보다 이 행동이 얼마나 더 나은가?

이 개념은 RL을 직접 구현하지 않아도 유용하다. 실행 로그를 분석하면서 어느 시점부터 성공 가능성이 떨어졌는지, 어떤 행동이 불필요했는지, 회복 불가능한 상태가 언제 만들어졌는지를 판단할 수 있기 때문이다.

또한 최종 성공 보상만 사용할지, 페이지 도달이나 필드 검증 같은 중간 신호를 사용할지도 판단할 수 있다. 단, 중간 신호를 잘못 설계하면 실제 목표가 아니라 쉬운 지표만 최적화하는 reward hacking이 발생할 수 있다.

### 4.3 Distribution shift와 학습 안정성

브라우저 에이전트가 사용할 수 있는 데이터는 서로 다른 분포를 가진다.

- 사람이 직접 수행한 작업
- 현재 버전 에이전트의 실행 로그
- 과거 버전 에이전트의 로그
- 성공 trajectory
- 실패 trajectory
- 웹사이트 변경 전후의 로그

이 데이터들은 모두 `(상태, 행동)` 형태로 저장될 수 있지만, 행동을 생성한 정책과 실행된 환경이 다르다.

예를 들어 과거 로그에 있던 selector가 현재 웹사이트에는 없을 수 있고, 사람이 수행한 행동 분포와 LLM 에이전트의 행동 분포가 다를 수 있다. 따라서 과거 로그를 현재 정책에 그대로 학습시키는 것은 단순한 데이터 추가가 아니다.

replay buffer는 단순한 저장소라기보다 다음 메타데이터를 포함한 실행 기록으로 이해하는 편이 적절하다.

- 어떤 정책이 생성했는가?
- 어떤 웹사이트와 UI 버전에서 생성했는가?
- 성공, 실패, 중단 중 어떤 결과였는가?
- 당시의 인증과 세션 상태는 무엇이었는가?

PPO의 clipping과 SAC의 replay 학습이 서로 다른 알고리즘인 동시에, 같은 문제를 다룬다. 즉, 과거 데이터를 재사용하면서 현재 정책과 데이터 생성 정책의 차이를 어떻게 관리할 것인가의 문제다.

## 5. 현업에서 얻는 실제 의미

이 강의의 현업적 의미는 PPO, SAC, DQN을 브라우저 에이전트에 무조건 도입하는 데 있지 않다. 핵심은 브라우저 에이전트의 문제를 다음 세 가지로 분류하고 분석하는 능력이다.

1. **상태 전이 문제**
   - 행동이 페이지를 예상과 다르게 바꾸었는가?
   - 한 번의 오류가 이후 trajectory를 망가뜨렸는가?

2. **기여도 판단 문제**
   - 긴 작업에서 어느 행동이 실패를 유발했는가?
   - 성공에 기여한 행동과 우연히 함께 나타난 행동을 구분할 수 있는가?

3. **데이터와 정책 변화 문제**
   - 현재 환경과 과거 로그의 환경이 같은가?
   - 과거 정책이 만든 행동을 현재 정책 학습에 사용해도 되는가?
   - 새로운 정책을 실제 환경에 바로 배포해도 되는가?

이렇게 보면 RL 개념은 새로운 학습 알고리즘을 추가하는 방법론이라기보다, 기존 에이전트의 실행 구조와 실패 로그를 해석하는 분석 프레임워크가 된다.

## 6. 결론

CS224R 1~6강은 다음 한 문장으로 요약할 수 있다.

> 에이전트의 행동이 환경과 이후 데이터 분포를 바꾸는 상황에서, 장기적인 결과를 이용해 어떤 행동을 유지하고 어떤 행동을 수정할지 학습하는 방법을 다룬다.

브라우저 조작 에이전트에 적용할 때 가장 중요한 통찰도 알고리즘 이름이 아니다.

- 에이전트는 단발성 입력-출력 모델이 아니라 폐루프 시스템이다.
- 최종 성공만으로는 중간 행동의 기여도를 판단하기 어렵다.
- 모든 실행 로그가 같은 분포와 신뢰도를 가지지 않는다.

따라서 브라우저 에이전트를 더 잘 만든다는 것은 단순히 더 정확한 클릭을 예측하는 것이 아니라, **상태 변화, 장기적인 행동 기여도, 데이터 생성 정책과 환경 변화까지 함께 이해하고 관리하는 것**이다.

## 7. 참고 자료

- [Stanford CS224R Spring 2025 공식 강의 페이지](https://cs224r.stanford.edu/spring_2025/)
- [Lecture 1: Course Introduction + MDPs](https://cs224r.stanford.edu/spring_2025/slides/01_cs224r_intro_2025.pdf)
- [Lecture 2: Imitation Learning](https://cs224r.stanford.edu/spring_2025/slides/02_cs224r_imitation_2025.pdf)
- [Lecture 3: Policy Gradients](https://cs224r.stanford.edu/spring_2025/slides/03_cs224r_policy_gradients_2025.pdf)
- [Lecture 4: Actor Critic Methods](https://cs224r.stanford.edu/spring_2025/slides/04_cs224r_actor_critic_2025.pdf)
- [Lecture 5: Off-Policy Actor Critic Methods](https://cs224r.stanford.edu/spring_2025/slides/05_cs224r_offpolicy_actor_critic_2025.pdf)
- [Lecture 6: Q-learning](https://cs224r.stanford.edu/spring_2025/slides/06_cs224r_qlearning_2025.pdf)

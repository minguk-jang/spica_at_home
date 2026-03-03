# 📚 Selector Collector v2 문서 색인

이 디렉토리에는 프로젝트의 모든 문서가 체계적으로 정리되어 있습니다.

---

## 🎯 각 문서의 용도

### 👤 사용자를 위한 문서

#### [README.md](./readme.md) - **여기서 시작하세요!**
- 📌 프로젝트 개요 및 주요 기능
- 🚀 빠른 시작 가이드
- 💡 사용 예시
- 🔒 개인정보 보호 정책
- 🐛 문제 해결

**추천 대상**: 확장을 처음 사용하는 사용자

---

### 👨‍💻 개발자를 위한 문서

#### [STRUCTURE.md](./STRUCTURE.md) - 프로젝트 구조 이해하기
- 📁 전체 디렉토리 구조
- 📝 각 파일의 용도 설명
- 🔄 데이터 흐름도
- 🔌 확장 프로그램 구조
- 💾 저장소 전략

**추천 대상**: 프로젝트 아키텍처를 이해하고 싶은 개발자

#### [IMPLEMENTATION.md](./IMPLEMENTATION.md) - 구현된 모든 기능
- 📦 각 모듈별 함수 목록
- 🔍 함수의 역할 및 기능
- 📊 구현 현황 요약
- ✅ 완료된 기능들만 정리

**추천 대상**: 기존 코드를 이해하고 수정해야 하는 개발자

#### [API.md](./API.md) - API 명세 및 인터페이스
- 🔧 각 모듈의 공개 API
- 📤 메시지 프로토콜
- 💬 메시지 흐름도
- 📋 사용 예시
- ✅ API 호환성 체크리스트

**추천 대상**: 모듈 간 통신을 이해하고 싶은 개발자

#### [ROADMAP.md](./ROADMAP.md) - 개발 계획 및 향후 기능
- 📅 Phase별 계획 (1-4)
- 🔴 우선순위별 작업 목록
- 🐛 알려진 버그 및 해결책
- ✅ 테스트 계획
- 📊 마일스톤

**추천 대상**: 프로젝트의 방향을 알고 싶거나 기여하고 싶은 개발자

---

## 📖 문서 구조

```
docs/
├── INDEX.md                  # 이 파일 - 문서 색인
├── README.md                 # 사용자 가이드 (필수)
├── STRUCTURE.md              # 프로젝트 구조 (필독)
├── IMPLEMENTATION.md         # 구현된 기능 (개발 시 참고)
├── API.md                    # API 명세 (통합 개발 시)
├── ROADMAP.md                # 개발 계획 (기여 시)
└── archive/
    └── implementation-plan.md # 초기 구현 계획 (참고용)
```

---

## 🎓 학습 경로

### 1️⃣ 프로젝트 이해하기
```
README.md → STRUCTURE.md → IMPLEMENTATION.md
```

### 2️⃣ 개발/수정하기
```
STRUCTURE.md → IMPLEMENTATION.md → API.md
```

### 3️⃣ 기여하기
```
README.md → ROADMAP.md → IMPLEMENTATION.md → 코드 수정
```

### 4️⃣ 디버깅하기
```
STRUCTURE.md → API.md → IMPLEMENTATION.md
```

---

## 📌 핵심 정보 빠르게 찾기

### "어디서 시작해야 하나?"
→ **[README.md](./readme.md)** 읽기

### "전체 구조가 어떻게 되나?"
→ **[STRUCTURE.md](./STRUCTURE.md)** 참고

### "이 함수가 뭐 하는 건데?"
→ **[IMPLEMENTATION.md](./IMPLEMENTATION.md)** 검색

### "두 모듈이 어떻게 통신하나?"
→ **[API.md](./API.md)** 확인

### "다음에 뭘 만들어야 하나?"
→ **[ROADMAP.md](./ROADMAP.md)** 참고

### "초기 구현 계획은?"
→ **[archive/implementation-plan.md](./archive/implementation-plan.md)**

---

## 📊 문서 요약표

| 문서 | 페이지 | 목적 | 대상 |
|------|--------|------|------|
| README | 5쪽 | 사용자 가이드 | 모든 사용자 |
| STRUCTURE | 5쪽 | 아키텍처 이해 | 개발자 |
| IMPLEMENTATION | 14쪽 | 함수 목록 | 개발자 |
| API | 9쪽 | API 명세 | 개발자 |
| ROADMAP | 8쪽 | 개발 계획 | 팀 리더 |

---

## 🔄 문서 관리

### 문서 업데이트 규칙

1. **IMPLEMENTATION.md**: 새 함수 추가/수정 시 즉시 업데이트
2. **API.md**: 메시지 프로토콜 변경 시 즉시 업데이트
3. **ROADMAP.md**: 2주마다 진행 상황 갱신
4. **STRUCTURE.md**: 파일 구조 변경 시만 업데이트

### 문서 아카이빙

- 더 이상 참고하지 않는 계획은 `archive/` 폴더로 이동
- 초기 구현 계획은 이미 아카이브됨

---

## 💡 팁

### 마크다운 링크
각 문서는 상호 참조됩니다. 문서 내의 링크를 클릭하면 관련 문서로 이동합니다.

### 검색 팁
```bash
# 특정 함수 찾기
grep -r "functionName" docs/

# 특정 개념 찾기
grep -r "selector validation" docs/
```

### VS Code에서
- `Ctrl+Shift+O`: 문서의 제목/섹션 목차 보기
- `Ctrl+F`: 문서 내 검색

---

## ✅ 문서 완성도

- ✅ README.md - 사용자 가이드 완성
- ✅ STRUCTURE.md - 프로젝트 구조 완성
- ✅ IMPLEMENTATION.md - 구현 함수 정리 완성
- ✅ API.md - API 명세 완성
- ✅ ROADMAP.md - 개발 계획 완성
- ✅ INDEX.md - 문서 색인 완성

**전체 50+ 개 함수/기능 문서화 완료** 🎉

---

## 📞 문의

각 문서에 대한 질문이나 오류를 발견하면, 해당 문서의 상단에 이슈를 남겨주세요.

---

**마지막 업데이트**: 2026-02-08

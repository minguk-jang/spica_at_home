# Selector Collector v2 - 사용자 가이드

> Chrome Extension으로 웹페이지의 요소를 클릭하면 모든 가능한 셀렉터를 자동으로 수집합니다.

## 🎯 주요 기능

### ✨ 강력한 셀렉터 수집
클릭한 요소의 다양한 선택자를 자동 생성합니다:
- **ID 선택자**: `#element-id`
- **클래스 선택자**: `.class1.class2`
- **속성 선택자**: `[data-testid="value"]`
- **XPath**: `//button[@id="login"]`
- **텍스트 기반**: `//button[contains(text(),'로그인')]`
- **Full Path**: `#app > div > button:nth-of-type(2)`

### 📜 히스토리 관리
- 최대 100개 수집 항목 자동 저장
- 각 항목의 모든 셀렉터 검토
- 유효성 실시간 검증 및 수동 토글 ✨ NEW
- 원클릭 복사 (텍스트 박스 클릭)
- Test 버튼으로 실제 요소 클릭 테스트 ✨ NEW

### 💾 데이터 저장
- 수집 데이터를 JSON으로 내보내기
- 로컬 파일 시스템에 직접 저장
- 권한 기반 안전한 저장

### 🎨 테마 전환 ✨ NEW
- **다크 테마 (Void)**: 전문적인 어두운 색상 팔레트
- **라이트 테마 (Stone)**: 부드러운 밝은 색상 팔레트
- 원클릭 테마 전환 (태양/달 아이콘)
- 사용자 설정 영구 저장
- 부드러운 전환 애니메이션
- 사이드패널 및 대시보드 모두 지원

### 📊 대시보드 관리 ✨ NEW
- **파일 목록**: 저장된 모든 JSON 파일 카드 뷰로 확인
- **상세 편집**: 각 entry의 셀렉터 값 및 메타데이터 인라인 수정
- **파일 간 이동**: 드래그 앤 드롭으로 entry를 다른 JSON으로 이동/복사
- **파일 삭제**: 불필요한 파일 삭제
- **순서 변경**: entry 순서 재배치

## 🚀 빠른 시작

### 1️⃣ 설치
1. Chrome에서 확장 프로그램 열기
2. 개발자 모드 활성화
3. 이 프로젝트를 "압축 해제된 확장 프로그램으로 로드"

### 2️⃣ 사용
1. 확장 아이콘 클릭
2. "Start Collecting" 버튼 클릭
3. 웹페이지에서 원하는 요소 클릭
4. 셀렉터들이 자동으로 수집됨
5. 필요시 "Save" 또는 "Export" 클릭

### 3️⃣ 데이터 내보내기
1. 사이드패널에서 "Export" 버튼 클릭
2. 저장할 디렉토리 선택
3. JSON 파일로 자동 저장됨

### 4️⃣ 대시보드 사용 ✨ NEW
1. 사이드패널에서 "Dashboard" 버튼 클릭
2. 새 탭에서 대시보드 페이지 열림
3. 저장된 JSON 파일 목록 확인

**파일 편집:**
- 파일 카드 클릭 또는 "Open" 버튼
- 각 entry의 셀렉터 값 수정
- "Save" 버튼으로 저장

**파일 간 이동:**
- "⇄" 버튼 클릭 (Move Mode)
- 좌/우 패널에서 각각 파일 선택
- entry를 드래그하여 반대 패널로 이동
- "Save Both" 버튼으로 양쪽 파일 저장

## 📚 문서

프로젝트의 자세한 정보는 다음 문서들을 참고하세요:

- **[STRUCTURE.md](./STRUCTURE.md)** - 프로젝트 구조 및 파일 설명
- **[IMPLEMENTATION.md](./IMPLEMENTATION.md)** - 구현된 모든 함수 및 기능
- **[API.md](./API.md)** - API 명세 및 메시지 프로토콜
- **[ROADMAP.md](./ROADMAP.md)** - 개발 계획 및 향후 기능

## 🏗️ 프로젝트 구조

```
selector_collector_ver2/
├── docs/                      # 📚 문서
│   ├── README.md             # 이 파일
│   ├── STRUCTURE.md          # 프로젝트 구조
│   ├── IMPLEMENTATION.md      # 구현된 기능
│   ├── API.md                # API 문서
│   └── ROADMAP.md            # 개발 계획
│
├── lib/                       # 🔧 유틸리티
│   ├── idb-helper.js         # IndexedDB 래퍼
│   └── fs-storage.js         # 파일 시스템 API
│
├── icons/                     # 🎨 아이콘
├── manifest.json             # 확장 설정
├── selector-core.js          # 셀렉터 엔진
├── content.js                # 콘텐츠 스크립트
├── background.js             # 서비스 워커
├── sidepanel.js              # 사이드패널 로직
├── sidepanel.html            # UI 마크업
├── sidepanel.css             # 스타일
├── dashboard.js              # 대시보드 로직 ✨
├── dashboard.html            # 대시보드 UI ✨
└── dashboard.css             # 대시보드 스타일 ✨
```

## 💡 사용 예시

### Web Testing Automation
Selenium, Cypress, Playwright 등의 테스트 자동화 도구에서 안정적인 셀렉터가 필요할 때 사용합니다.

```javascript
// Selenium Example
const button = driver.find_element("css selector", "#submit-btn")

// 또는 XPath
const button = driver.find_element("xpath", "//button[@id='submit']")
```

### Web Scraping
웹 크롤러에서 정확한 요소 선택자가 필요할 때:

```python
# BeautifulSoup / Selenium
elements = driver.find_elements("css selector", ".product-item")
```

### 개발자 도구
웹 개발 중 요소 선택에 어려움이 있을 때 빠르게 여러 셀렉터를 시도해볼 수 있습니다.

## ⚡ 팁 및 트릭

1. **여러 셀렉터 생성**: 한 번의 클릭으로 8가지 이상의 셀렉터 자동 생성
2. **유효성 검증**: 생성된 셀렉터의 유효성 자동 확인 (✓/✗)
3. **유효성 수동 토글**: ✓/✗ 아이콘 클릭으로 Test 결과에 따라 수동 수정 ✨ NEW
4. **Test 버튼**: Test 클릭 → 셀렉터로 요소를 찾아 실제 클릭 실행 ✨ NEW
5. **빠른 복사**: 셀렉터 텍스트 클릭 또는 Test 버튼으로 즉시 클립보드 복사
6. **히스토리 관리**: 이전 클릭 항목들을 언제든 다시 확인 가능
7. **JSON 내보내기**: 모든 수집 데이터를 JSON으로 저장하여 재사용
8. **테마 전환**: 헤더의 테마 토글 버튼으로 다크/라이트 모드 변경
9. **대시보드 관리**: Dashboard에서 JSON 파일 편집, 삭제, 파일 간 이동 가능

## 🔒 개인정보 보호

- 모든 데이터는 **로컬에만 저장**됩니다
- 클라우드로 전송되지 않습니다
- 사용자가 명시적으로 "Export"할 때만 파일로 저장됩니다
- 언제든 히스토리 전체 삭제 가능합니다

## 🐛 문제 해결

### 확장이 제대로 로드되지 않음
- manifest.json 문법 확인
- Chrome 버전 90 이상 필요
- 개발자 모드 활성화 필수

### 셀렉터가 수집되지 않음
1. "Start Collecting" 활성화 확인
2. 웹페이지가 보안 페이지(HTTPS)인지 확인
3. 새로고침(Ctrl+R) 후 다시 시도

### 파일 저장이 안 됨
1. "Select Directory" 버튼으로 디렉토리 선택
2. 폴더 쓰기 권한 확인
3. 브라우저 권한 설정 확인

## 🤝 기여

이 프로젝트의 개선사항이나 버그 리포트는 언제든 환영합니다!

## 📖 추가 참고

- [Chrome Extension Documentation](https://developer.chrome.com/docs/extensions/)
- [MDN - CSS Selectors](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Selectors)
- [MDN - XPath](https://developer.mozilla.org/en-US/docs/Web/XPath)

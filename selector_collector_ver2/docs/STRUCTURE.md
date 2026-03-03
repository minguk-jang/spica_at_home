# 프로젝트 구조

## 📁 디렉토리 구조

```
selector_collector_ver2/
├── docs/                      # 📚 문서
│   ├── README.md             # 사용자 가이드
│   ├── STRUCTURE.md          # 프로젝트 구조 (이 파일)
│   ├── IMPLEMENTATION.md      # 구현된 기능 목록
│   ├── API.md                # API 문서
│   └── ROADMAP.md            # 개발 계획
│
├── lib/                       # 🔧 유틸리티 라이브러리
│   ├── idb-helper.js         # IndexedDB 래퍼
│   └── fs-storage.js         # File System Access API 래퍼
│
├── icons/                     # 🎨 확장 프로그램 아이콘
│   ├── icon16.png
│   ├── icon32.png
│   ├── icon48.png
│   └── icon128.png
│
├── references/               # 📖 참고 자료
│
├── manifest.json             # Chrome Extension 설정
├── background.js             # 🖥️ Service Worker (확장 백그라운드)
├── content.js                # 📄 Content Script (웹페이지에 주입)
├── selector-core.js          # 🔍 셀렉터 생성 엔진
├── sidepanel.html            # 🎛️ 사이드패널 UI 마크업
├── sidepanel.css             # 🎨 사이드패널 스타일
├── sidepanel.js              # ⚙️ 사이드패널 로직
├── dashboard.html            # 📊 대시보드 UI 마크업
├── dashboard.css             # 🎨 대시보드 스타일
└── dashboard.js              # 📊 대시보드 로직 (파일 관리/편집/이동)
```

## 📝 파일 설명

### 핵심 모듈

| 파일 | 용도 | 설명 |
|------|------|------|
| `manifest.json` | 설정 | Chrome Extension 메니페스트 (Manifest V3) |
| `selector-core.js` | 엔진 | 웹 요소에서 다양한 셀렉터를 생성하는 핵심 엔진 |
| `content.js` | 콘텐츠 | 웹페이지에서 클릭 이벤트 감지 및 셀렉터 수집 |
| `background.js` | 서비스워커 | 탭 관리, 메시지 라우팅, 상태 관리 |
| `sidepanel.html` | UI | 사이드패널 HTML 마크업 |
| `sidepanel.js` | UI로직 | 사이드패널 상호작용 및 상태 관리 |
| `sidepanel.css` | 스타일 | 사이드패널 시각 스타일 |
| `dashboard.html` | UI | 대시보드 HTML 마크업 (별도 페이지) |
| `dashboard.js` | 대시보드 | JSON 파일 관리, 편집, 드래그 앤 드롭 이동 |
| `dashboard.css` | 스타일 | 대시보드 시각 스타일 (GitHub Dark 테마) |

### 유틸리티 라이브러리

| 파일 | 용도 | 설명 |
|------|------|------|
| `lib/idb-helper.js` | 저장소 | IndexedDB 데이터베이스 접근 추상화 |
| `lib/fs-storage.js` | 저장소 | 파일 시스템 API와 디렉토리 관리 |

### 리소스

| 디렉토리 | 용도 | 설명 |
|---------|------|------|
| `icons/` | 아이콘 | 확장 프로그램 아이콘 (16, 32, 48, 128px) |
| `references/` | 참고 | 개발 중 참고했던 문서 및 자료 |
| `docs/` | 문서 | 프로젝트 문서 및 개발 계획 |

## 🔄 데이터 흐름

### 셀렉터 수집 흐름
```
사용자 클릭
    ↓
content.js (클릭 감지)
    ↓
selector-core.js (셀렉터 생성)
    ↓
background.js (메시지 포워딩)
    ↓
sidepanel.js (UI 업데이트, 히스토리 저장)
    ↓
저장소
  ├─ IndexedDB (idb-helper.js)
  └─ 파일 시스템 (fs-storage.js)
```

### 대시보드 관리 흐름
```
사용자 "Dashboard" 버튼 클릭
    ↓
sidepanel.js (chrome.tabs.create)
    ↓
dashboard.html/js 열림
    ↓
fs-storage.js (listJsonFiles, readJson)
    ↓
파일 시스템에서 JSON 파일 목록 로드
    ↓
사용자 편집/이동/삭제
    ↓
fs-storage.js (saveJson, deleteFile)
    ↓
파일 시스템에 저장
```

## 🔌 확장 프로그램 구조

### 컨텐츠 스크립트 (Content Script)
- 웹페이지에 주입되어 클릭 이벤트 감지
- `selector-core.js` 사용하여 셀렉터 생성
- 메시지를 통해 Service Worker와 통신

### Service Worker (Background Script)
- 탭 관리 및 상태 추적
- 콘텐츠 스크립트 ↔ 사이드패널 메시지 라우팅
- 단일 활성 탭만 수집 가능하도록 관리

### 사이드패널 (Side Panel)
- 확장 프로그램 UI 제공
- 수집 시작/중지 제어
- 히스토리 표시 및 관리
- 파일 내보내기 기능

## 💾 저장소 전략

### IndexedDB (`idb-helper.js`)
- 용도: 확장 프로그램 상태 및 설정 저장
- 저장 항목:
  - 디렉토리 핸들 (File System Access API)
  - 히스토리 데이터
  - 사용자 설정

### 파일 시스템 (`fs-storage.js`)
- 용도: 수집 데이터를 JSON으로 로컬 파일에 저장
- File System Access API 사용
- 사용자가 선택한 디렉토리에만 저장 가능

## 🚀 실행 흐름 (사용자 관점)

### 셀렉터 수집 흐름
1. 확장 프로그램 활성화
2. 사이드패널에서 "Start Collecting" 클릭
3. 웹페이지에서 요소 클릭
4. 각 클릭마다 모든 가능한 셀렉터 자동 수집
5. 히스토리에서 검토
6. "Save" 버튼으로 JSON 파일로 내보내기

### 대시보드 관리 흐름
1. 사이드패널에서 "Dashboard" 버튼 클릭
2. 새 탭에서 대시보드 페이지 열림
3. 저장된 JSON 파일 목록 확인
4. 파일 열기:
   - 개별 entry 수정 (셀렉터 값, 메타데이터)
   - entry 삭제, 순서 변경
   - 수정 후 "Save" 버튼 클릭
5. "Move Mode" 사용:
   - 두 JSON 파일을 나란히 열기
   - 드래그 앤 드롭으로 entry 이동/복사
   - "Save Both" 버튼으로 저장

## 📌 주요 개념

### 셀렉터 종류
- **ID Selector**: `#login-btn`
- **Class Selector**: `.btn.btn-primary`
- **Tag Selector**: `button`
- **Attribute Selector**: `button[data-testid="submit"]`
- **nth-of-type**: `div:nth-of-type(3)`
- **Full CSS Path**: `#app > div > button:nth-child(2)`
- **XPath**: `//button[@id="login"]`
- **Text XPath**: `//button[contains(text(),'로그인')]`

### 상태 관리
- 한 번에 **한 탭**만 수집 활성
- 탭 전환 시 자동으로 수집 상태 동기화
- 탭 종료 시 수집 자동 중지

# 구현 계획: 저장 Modal + 대시보드 편집 기능

> 작성일: 2026-02-08
> 상태: ✅ **구현 완료** (2026-02-08)
>
> **구현된 기능:**
> - ✅ 저장 Modal (이름 입력, 요약 정보, 파일명 검증)
> - ✅ 대시보드 파일명 Rename
> - ✅ Entry 정보 편집 (Tag, Text, URL)
> - ✅ 파일 카드에 name 표시
> - ✅ FsStorage.renameFile() 구현

---

## 1. 저장 Modal 구현

### 1-1. 요구사항

현재 sidepanel에서 Save 버튼 클릭 시 **이름 없이 타임스탬프 기반 파일명으로 바로 저장**되는 문제를 개선한다.

**변경 후 흐름:**
1. Save 버튼 클릭
2. Modal이 열림
3. Modal에 표시되는 내용:
   - **이름 입력 필드**: 사용자가 원하는 이름 입력 (예: "login-page")
   - **저장 요약 정보**: 총 entry 수, 수집된 URL 목록, 태그 분포
4. 확인 버튼 클릭 시 저장 실행
5. 취소 버튼 클릭 시 Modal 닫힘

### 1-2. 파일명 규칙

- 파일명 형식: `selectors-{사용자입력이름}-{타임스탬프}.json`
- 예시: `selectors-login-page-2026-02-08T11-28-00.json`
- `selectors-` prefix는 유지하여 대시보드에서의 파일 탐색 호환성 보장
- 사용자가 이름을 비워두면 기존처럼 타임스탬프만 사용
- **허용 문자**: 영문(a-z, A-Z), 숫자(0-9), 하이픈(-) 만 허용
- **한글 불허**: 한글 및 기타 특수문자 입력 시 제거 또는 입력 차단
- **검증 정규식**: `/^[a-zA-Z0-9-]+$/`
- 입력 필드에 실시간 검증 표시 (유효하지 않은 문자 입력 시 경고)

### 1-3. JSON 내부 데이터 구조 변경

```json
{
  "name": "login-page",
  "exportedAt": "2026-02-08T11:28:00.000Z",
  "totalEntries": 5,
  "entries": [...]
}
```

- `name` 필드 추가: 사용자가 입력한 이름 저장
- 대시보드에서 파일 카드 표시 시 `name` 필드가 있으면 파일명 대신 표시 가능

### 1-4. Modal UI 설계

```
┌─────────────────────────────────────┐
│  셀렉터 저장                     [X] │
├─────────────────────────────────────┤
│                                     │
│  이름                               │
│  ┌─────────────────────────────────┐│
│  │ login-page                      ││
│  └─────────────────────────────────┘│
│                                     │
│  ── 저장 요약 ───────────────────── │
│                                     │
│  총 entry 수: 5개                   │
│  수집 URL:                          │
│    • https://example.com/login      │
│    • https://example.com/signup     │
│  태그 분포:                         │
│    button(3), input(1), a(1)        │
│                                     │
├─────────────────────────────────────┤
│              [취소]    [저장]        │
└─────────────────────────────────────┘
```

### 1-5. 구현 위치 및 파일

| 작업 | 파일 | 설명 |
|------|------|------|
| Modal HTML 마크업 | `sidepanel.html` | body 내부에 modal overlay + modal content 추가 |
| Modal CSS 스타일 | `sidepanel.css` | overlay, modal-content, 입력 필드, 버튼 스타일 |
| Modal 로직 | `sidepanel.js` | 열기/닫기, 요약 데이터 계산, 저장 실행 |

### 1-6. 구현 단계

**Step 1: Modal HTML 추가** (`sidepanel.html`)
- `</body>` 직전에 modal overlay div 추가
- 내부: 제목, 이름 input, 요약 정보 영역, 취소/저장 버튼

**Step 2: Modal CSS 추가** (`sidepanel.css`)
- `.modal-overlay`: position fixed, 전체 화면 배경 반투명
- `.modal-content`: 중앙 배치, 기존 테마(GitHub Dark) 유지
- `.modal-input`: 이름 입력 필드 스타일
- `.modal-summary`: 요약 정보 영역 스타일
- `.modal-footer`: 버튼 영역

**Step 3: 저장 로직 변경** (`sidepanel.js`)
- `savBtn` 이벤트 핸들러 변경: 바로 저장 → Modal 열기
- 새 함수 `openSaveModal()`: Modal을 열고 요약 정보 계산하여 표시
  - 총 entry 수: `history.length`
  - URL 목록: `history`에서 `elementInfo.url`을 Set으로 중복 제거
  - 태그 분포: `history`에서 `elementInfo.tagName` 빈도 계산
- 새 함수 `closeSaveModal()`: Modal 닫기
- `confirmSave()`: 이름 가져와서 파일명 생성 → `FsStorage.saveJson()` 호출
- Escape 키, overlay 클릭으로도 Modal 닫기

### 1-7. 요약 정보 계산 로직

```javascript
// 의사 코드
function calculateSummary(history) {
  const urls = [...new Set(history.map(e => e.elementInfo?.url).filter(Boolean))];
  const tagCounts = {};
  history.forEach(e => {
    const tag = e.elementInfo?.tagName || 'UNKNOWN';
    tagCounts[tag] = (tagCounts[tag] || 0) + 1;
  });
  return { totalEntries: history.length, urls, tagCounts };
}
```

---

## 2. 대시보드 편집 기능 확장

### 2-1. 요구사항

현재 대시보드 상세 뷰에서 **셀렉터 값만 편집 가능**하고, 다음은 읽기 전용:
- 파일 이름 (카드의 제목)
- 각 entry의 Tag, Text, URL (`elementInfo` 필드)

**변경 후:** 모두 편집 가능하게 한다.

### 2-2. 파일명 수정 (Rename)

#### UI
- 파일 카드의 파일명 옆에 **Rename 버튼** 추가
- 클릭 시 파일명이 **인라인 input**으로 변경
- Enter 또는 blur 시 저장, Escape 시 취소

#### 로직
- `FsStorage`에 `renameFile(oldName, newName)` 함수 추가 필요
  - File System Access API에는 rename이 없으므로:
    1. 기존 파일 읽기 (`readJson`)
    2. 새 파일명으로 저장 (`saveJson`)
    3. 기존 파일 삭제 (`deleteFile`)
  - JSON 내부 `name` 필드도 함께 업데이트
- 파일명 규칙 검증: `selectors-` prefix 유지, 특수문자 제거

#### 구현 위치

| 작업 | 파일 |
|------|------|
| Rename 버튼 UI | `dashboard.js` - `renderFileCards()` 내 |
| 인라인 편집 로직 | `dashboard.js` - 새 함수 `startRename()`, `confirmRename()` |
| 파일 rename 함수 | `lib/fs-storage.js` - `renameFile()` 추가 |
| Rename 버튼 스타일 | `dashboard.css` |

### 2-3. Entry 정보 편집 (Tag, Text, URL)

#### UI 변경

현재 (읽기 전용):
```html
<span class="info-value">${entry.elementInfo?.tagName || '-'}</span>
```

변경 후 (편집 가능):
```html
<input type="text" class="info-input" value="${entry.elementInfo?.tagName || ''}"
       data-field="tagName" data-entry-index="${index}">
```

세 필드 모두 `<span>` → `<input>`으로 변경:
- **Tag**: `entry.elementInfo.tagName`
- **Text**: `entry.elementInfo.textContent`
- **URL**: `entry.elementInfo.url`

#### 로직 변경

`dashboard.js`의 `createEntryElement()` 함수 내:
1. `info-value` span을 `info-input` input으로 교체
2. `change` 이벤트 리스너 추가하여 `currentData[index].elementInfo[field]` 업데이트
3. 기존 Save 버튼 로직은 이미 `currentData`를 통째로 저장하므로 추가 수정 불필요

#### 구현 위치

| 작업 | 파일 |
|------|------|
| info-value → info-input 변경 | `dashboard.js` - `createEntryElement()` (라인 296~307) |
| change 이벤트 리스너 추가 | `dashboard.js` - `createEntryElement()` 내 |
| input 스타일 | `dashboard.css` - `.info-input` 클래스 추가 |

### 2-4. 파일 카드에 name 표시

- JSON 내부에 `name` 필드가 있으면 카드 제목에 **name (파일명)** 형식으로 표시
- `name`이 없으면 기존처럼 파일명만 표시

---

## 3. 구현 순서 (권장)

| 순서 | 작업 | 예상 난이도 |
|------|------|-----------|
| 1 | Modal CSS 스타일 작성 | 낮음 |
| 2 | Modal HTML 마크업 추가 | 낮음 |
| 3 | Modal 열기/닫기 로직 (`sidepanel.js`) | 낮음 |
| 4 | 요약 정보 계산 및 표시 | 중간 |
| 5 | 이름 기반 저장 로직 변경 | 중간 |
| 6 | 대시보드 entry 편집 (Tag/Text/URL) | 낮음 |
| 7 | `FsStorage.renameFile()` 구현 | 중간 |
| 8 | 대시보드 파일명 rename UI/로직 | 중간 |
| 9 | 대시보드 카드에 name 필드 표시 | 낮음 |

---

## 4. 영향 범위

### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `sidepanel.html` | Modal HTML 마크업 추가 |
| `sidepanel.css` | Modal 관련 스타일 추가 |
| `sidepanel.js` | Save 로직 변경, Modal 함수 추가 |
| `dashboard.js` | entry 편집 input 변경, rename 기능, name 표시 |
| `dashboard.css` | info-input, rename 버튼 스타일 |
| `lib/fs-storage.js` | `renameFile()` 함수 추가 |

### 호환성 고려
- 기존에 `name` 필드 없이 저장된 JSON 파일과의 하위 호환성 유지
- `name` 없으면 기존 동작 그대로 유지
- 파일명 `selectors-` prefix 규칙 유지로 대시보드 파일 탐색 호환

---

## 5. 리스크

| 리스크 | 대응 |
|--------|------|
| File System Access API에 rename 없음 | 읽기→새로저장→삭제 3단계로 구현 |
| 파일명에 허용되지 않는 문자 입력 | 영문/숫자/하이픈만 허용, 그 외 실시간 차단 (`/^[a-zA-Z0-9-]+$/`) |
| Modal이 sidepanel 좁은 공간에 맞지 않을 수 있음 | 최소 너비 확인, 스크롤 가능하게 |
| 기존 JSON 파일에 name 필드 없음 | optional 처리, fallback으로 파일명 사용 |

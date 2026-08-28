# 다른 세션의 완료·검증 동작 교차검증

## 조사 범위와 방법

- `/Users/mingukjang/.aside/u/0/state.db`의 `sessions.system_prompt`를 세션별로 비교했다.
- `/Users/mingukjang/.aside/u/0/sessions/*/messages.jsonl`에서 assistant가 실제로 발행한 도구 호출만 추려 Todo 전이와 후속 검증 호출을 비교했다. 도구 결과에 포함된 문자열은 모델의 호출 증거로 세지 않았다.
- `/Users/mingukjang/.aside/logs/daemon-*.log`와 세션 runtime config에서 완료 알림 및 별도 postcondition/verify hook의 흔적을 확인했다.

## 프롬프트 반복 여부

프롬프트가 저장된 26개 세션 중 20개의 full/root prompt는 길이 19,810~22,167자였고, 모두 다음 항목을 포함했다.

- `Completion and Verification`
- `write_todos`
- 필요한 외부 side effect 확인

반면 6개의 약 1,437자 child/audit prompt에는 이 공통 완료 정책이 없었다. 따라서 이 정책은 모든 Aside 실행 단위에 자동으로 붙는 규칙이라기보다 full/root 세션에 주입되는 공통 system prompt의 특성으로 보인다.

## 실제 도구 호출 비교

| 세션 | 관찰된 마지막 확인 흐름 | 해석 |
|---|---|---|
| `2TNOGRTe2OPsUVRP` | `git push` 뒤 GitHub 페이지 `reload`/`snapshot`, 이어서 `git status`, `HEAD`, `origin/main`, `git show --stat`; 이 흐름이 여러 작업에서 반복됨 | 가장 강한 “외부 side effect 재확인” 사례. 모델이 일반 `repl`/`bash` 호출을 생성했다. |
| `LrIitPpOkUtYKUba` | `git push` 뒤 `fetch`, `rev-parse`, `status`를 한 `bash` 흐름에서 확인. GitHub 브라우저 snapshot은 없음 | 검증은 있었지만 페이지 재확인은 없음. |
| `uCqtjLeE4uaFhv6o` | commit/push 뒤 `fetch`, `rev-list`/log/status 계열 확인. 최종 push 뒤 GitHub snapshot은 없음 | 명령줄 검증을 선택한 사례. |
| `lqqY3NhoZSy3dlI7` | 보고서 작성·commit·push 후 remote commit 결과를 `bash` 출력으로 확인 | 최소한의 원격 상태 확인만 수행. |
| `Mb8Qb67RAJFlba7y`, `QGNmRbEeQ23IJvrG`, `vsHJllAQiAOh5eAA` | 명시적인 최종 `verify` Todo가 없거나, 작업 자체의 재조회/재검토로 종료 | Todo의 `completed` 전이와 별도 검증 프로세스가 일대일로 연결되지 않음. |

특히 `2TNOGRTe2OPsUVRP`에서는 `verify` 또는 `verify-update` Todo가 마지막에 `completed`로 바뀌었지만, 그 전후의 GitHub snapshot과 git 명령은 `write_todos`가 자동 실행한 내부 단계가 아니라 assistant tool call로 기록되어 있다. 반대로 다른 Git 세션에서는 같은 프롬프트를 가지고도 브라우저 확인 없이 명령줄 확인만 하거나, 확인 수준이 더 낮았다.

## 데몬/런타임 확인

데몬 로그에서 반복적으로 확인되는 `TaskCompletionNotification`은 sound/send/read 상태를 처리하는 완료 알림이다. 조사한 로그와 대상 세션의 runtime config에는 사용자 요청의 acceptance criteria를 자동 판정하는 별도 이벤트나 설정이 없었다. 설치 바이너리 문자열 검색에서도 `verify_request`, `pre_user_turn` 같은 이 흐름을 특정하는 전용 식별자는 확인되지 않았다. 단, `postcondition`처럼 라이브러리에서 쓰이는 일반 문자열은 바이너리에 존재할 수 있으므로 문자열 검색만으로 내부 동작의 부재를 증명할 수는 없다.

대상 세션의 runtime config에는 `finalConfirm: false`가 기록되어 있었다. 이 값과 완료 알림은 사용자 요청의 실제 달성 여부를 판정하는 검증기라는 증거가 아니다.

## 결론

“마지막 검증 프로세스가 prompt에만 적혀 있는가?”에 대한 답은 다음처럼 구분해야 한다.

1. 검증해야 한다는 **정책과 판단 기준은 prompt에 있다.**
2. 실제 검증 명령과 페이지 재조회는 **모델이 일반 도구 호출로 수행한다.** 실제 외부 상태를 읽기 때문에 단순히 prompt 텍스트만 있는 것은 아니다.
3. 그러나 모든 세션에서 동일한 검증을 강제하는 **관찰 가능한 자동 verifier/hook은 확인되지 않았다.** `write_todos`도 검증 명령, 증거, acceptance criteria와 기계적으로 연결되어 있지 않다.
4. 따라서 이 구조는 “prompt가 유도하는 모델 수준의 검증”이지, “런타임이 완료를 차단하기 전에 postcondition을 강제하는 검증 프로세스”로 보기는 어렵다.

이는 조사한 세션·로그·설정·설치 바이너리에서 확인한 범위의 결론이다. 바이너리에 기록되지 않은 비공개 동작이 없다는 것까지 증명하는 것은 아니다.

## 재현에 사용한 주요 근거

- 전체 prompt 비교: `SELECT id, length(system_prompt), instr(lower(system_prompt), 'before reporting completion'), instr(lower(system_prompt), 'write_todos'), instr(lower(system_prompt), 'external side effect') FROM sessions WHERE system_prompt <> '';`
- 도구 흐름: 각 세션의 `messages.jsonl`에서 `role=assistant`의 `tool_use`만 추출
- 완료 알림: `/Users/mingukjang/.aside/logs/daemon-*.log`의 `TaskCompletionNotification` 검색

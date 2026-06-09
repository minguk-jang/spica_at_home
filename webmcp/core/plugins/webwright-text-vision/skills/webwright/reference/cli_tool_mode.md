# CLI Tool Mode

`/webwright:run`은 사용자가 준 literal 값으로 한 번 실행되는 `final_script.py`를
만듭니다. 반면 `/webwright:craft`는 같은 종류의 작업을 다른 값으로 다시 실행할
수 있는 parameterized CLI tool을 만듭니다.

## 사용 시점

다음 요청이면 CLI tool mode를 사용합니다.

- 사용자가 `/webwright:craft`를 호출한다.
- “재사용 가능하게”, “parameterize”, “CLI로 만들기”, “다른 값으로 다시 호출하고
  싶다”처럼 변동 가능한 입력을 요구한다.

그 외에는 one-shot mode를 유지합니다.

## `plan.md` 요구사항

script를 쓰기 전에 `# Parameters` 섹션을 추가합니다. 사용자가 바꿀 수 있는 모든
값을 parameter로 식별하고, 각 parameter가 function argument와 `argparse --flag`
둘 다로 이어지게 합니다. 사이트 이름, start URL, selector strategy처럼 사이트
구조상 고정인 값은 parameter가 아닙니다.

```markdown
# Task
<사용자 요청 원문>

# Parameters
| name | type | source phrase | default | format |
|------|------|---------------|---------|--------|
| query | str | "..." | "삼성전자" | 회사명 |

# Critical Points
- [ ] CP1: ...
```

## `final_script.py` 모양

1. 작업 도메인을 나타내는 reusable function을 둡니다.
2. Google-style docstring에 summary, `Args:`, `Returns:`를 작성합니다.
3. `if __name__ == "__main__":` 아래에서 `argparse` CLI를 구성합니다.
4. module import 시점에는 브라우저 실행, 네트워크 호출, 파일 쓰기를 하지 않습니다.
5. action log 첫 줄은 `step 0 params: name=value ...` 형식이어야 합니다.
6. viewport는 1280x1800을 사용하고, screenshot은 `final_runs/run_<id>/screenshots`
   아래에 저장합니다.

```python
def lookup_stock(company_name: str, ticker: str) -> dict:
    """Naver에서 회사 주가 정보를 조회한다.

    Args:
        company_name: 검색할 회사명. Default: "삼성전자".
        ticker: 종목 코드. Default: "005930".

    Returns:
        dict with current_price, change_text, ticker.
    """
```

## 검증

새 `final_runs/run_<id>/`에서 argument 없이 실행해 원래 task를 재현해야 합니다.
그 다음 적어도 하나의 argument를 바꿔 다시 실행하고, action log의 parameter echo와
결과가 바뀐 입력을 반영하는지 확인합니다.

완료 전에는 모든 critical point가 text evidence 또는 vision fallback judgment를
가져야 합니다. Screenshot path만으로 성공을 주장하지 않습니다.

export type CoreLogicStage = {
  id: "request" | "create" | "store" | "run" | "jsTool" | "evaluate" | "memory";
  title: string;
  summary: string;
  detail: string;
  accent: "blue" | "green" | "orange";
};

export type DesktopTabGuide = {
  title: string;
  role: string;
  usage: string;
};

export type LandingMetricItem = {
  id: "workflows" | "pageMemory" | "knowledge" | "evaluator";
  label: string;
  description: string;
};

export const coreLogicStages: CoreLogicStage[] = [
  {
    id: "request",
    title: "요청",
    summary: "시작 URL, 사람이 원하는 태스크, 기대하는 최종 브라우저 상태가 Core로 들어옵니다.",
    detail: "처음부터 도메인별 필드를 요구하지 않고, 생성된 워크플로우 스키마에서 필요한 인자를 추론합니다.",
    accent: "blue"
  },
  {
    id: "create",
    title: "생성",
    summary: "브라우저 추적, 페이지 텍스트, 저장된 지식을 바탕으로 재사용 가능한 워크플로우 초안을 만듭니다.",
    detail: "안정적인 대기 조건, 동적 브라우저 액션, 핸들러, 인자, 리포트 리소스를 함께 구성합니다.",
    accent: "green"
  },
  {
    id: "store",
    title: "저장",
    summary: "워크플로우 도구, 버전, 스텝, 인자, 핸들러, 리소스, 실행 기록을 SQLite에 저장합니다.",
    detail: "데스크톱 앱은 기본적으로 ~/.webmcp-studio/db/workflows.sqlite에 있는 Studio DB를 읽습니다.",
    accent: "orange"
  },
  {
    id: "run",
    title: "실행",
    summary: "고정 스텝은 그대로 실행하고, 가변 UI 스텝은 실행 시점에 LLM이 코드를 생성합니다.",
    detail: "광고 닫기, 팝업, 페이지마다 달라지는 컨트롤은 런타임 생성 액션으로 표시해 처리합니다.",
    accent: "blue"
  },
  {
    id: "jsTool",
    title: "JS 변환",
    summary: "검증된 workflow tool을 Node.js에서 실행 가능한 JavaScript tool 산출물로 변환합니다.",
    detail: "manifest.json, workflow.json, tool.cjs를 만들고 run/eval 명령으로 출력 contract를 테스트합니다.",
    accent: "orange"
  },
  {
    id: "evaluate",
    title: "평가",
    summary: "각 실행은 브라우저 증거와 eval-and-evolve 검증으로 마무리될 수 있습니다.",
    detail: "Codex VLM은 스크린샷, URL/제목, 페이지 텍스트, 출력, 기대 상태를 보고 수정 여부를 판단합니다.",
    accent: "green"
  },
  {
    id: "memory",
    title: "메모리",
    summary: "성공한 실행 흔적은 다음 생성을 위한 페이지 분석과 스크립트 생성 지식으로 남습니다.",
    detail: "안정적인 마커, 셀렉터 전략, 위험 요소, 예시, 실패 모드가 다음 워크플로우 합성에 재사용됩니다.",
    accent: "orange"
  }
];

export const desktopTabGuides: DesktopTabGuide[] = [
  {
    title: "홈(Home)",
    role: "제품의 전체 흐름을 빠르게 파악하는 진입 화면입니다.",
    usage: "Core 생명주기를 확인한 뒤 생성, 워크플로우 확인, 메모리 검토 화면으로 바로 이동합니다."
  },
  {
    title: "워크플로우(Workflows)",
    role: "Studio DB에 저장된 WebMCP 워크플로우를 운영하는 목록입니다.",
    usage: "워크플로우를 선택해 headed 실행, eval-and-evolve, 새 워크플로우 생성을 시작합니다."
  },
  {
    title: "스텝(Steps)",
    role: "선택한 버전이 어떤 순서와 조건으로 실행되는지 보여주는 실행 지도입니다.",
    usage: "실행 전에 순서, 필수 인자, 동적 스텝, 핸들러, assertion을 점검합니다."
  },
  {
    title: "스크립트(Script)",
    role: "생성된 구현을 읽기 쉽게 확인하는 미리보기 영역입니다.",
    usage: "DB row를 직접 수정하지 않고 Playwright 스타일 미리보기와 핸들러 소스를 확인합니다."
  },
  {
    title: "JS 도구(JS Tool)",
    role: "선택한 workflow tool을 JavaScript tool로 변환하고 실행 contract를 테스트하는 작업 공간입니다.",
    usage: "버전 export 후 arguments JSON으로 run/eval을 실행하고 required output key 누락 여부를 확인합니다."
  },
  {
    title: "버전(Versions)",
    role: "워크플로우의 변경 이력과 실행 가능한 버전을 관리합니다.",
    usage: "버전을 전환하고 요약을 비교한 뒤 특정 버전을 headed 모드로 실행합니다."
  },
  {
    title: "업데이트(Update)",
    role: "실패 수정과 워크플로우 진화를 다루는 작업 공간입니다.",
    usage: "수정 요청을 적고 Codex 제안을 생성한 뒤 증거를 검토하고 draft 버전을 적용합니다."
  },
  {
    title: "실행 기록(Runs)",
    role: "실행 결과, 증거, 출력 이력을 확인하는 감사 로그입니다.",
    usage: "결과 요약, 리포트, 스텝 증거, 상태, 시간, 중단된 실행 기록을 검토합니다."
  },
  {
    title: "메모리(Memory)",
    role: "페이지 분석과 재사용 가능한 스크립트 지식을 모아둔 저장소입니다.",
    usage: "안정적인 대기 조건, 셀렉터 전략, 위험 메모, 지식 팁, 저장된 예시를 검색합니다."
  }
];

export const landingMetricItems: LandingMetricItem[] = [
  {
    id: "workflows",
    label: "워크플로우 도구",
    description: "Studio DB에 저장되어 바로 실행할 수 있는 자동화입니다."
  },
  {
    id: "pageMemory",
    label: "페이지 분석",
    description: "대기 조건, 셀렉터, 위험 요소를 포함한 관찰된 페이지 형태입니다."
  },
  {
    id: "knowledge",
    label: "지식 팁",
    description: "이전 실행에서 얻은 재사용 가능한 스크립트 생성 지식입니다."
  },
  {
    id: "evaluator",
    label: "평가 모델",
    description: "Codex VLM이 브라우저 증거와 수정 초점을 검증합니다."
  }
];

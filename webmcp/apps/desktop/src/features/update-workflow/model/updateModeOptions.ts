export type UpdateMode = "code-only" | "browser";
export type UpdateDiscoveryProvider = "none" | "static" | "webwright";

export type UpdateModeOption = {
  mode: UpdateMode;
  label: string;
  description: string;
  discoveryProvider: UpdateDiscoveryProvider;
};

export const UPDATE_MODE_OPTIONS: UpdateModeOption[] = [
  {
    mode: "code-only",
    label: "코드만 보고 수정",
    description: "저장된 workflow JSON, 스텝, 구현 정보와 수정 지시만 보고 draft를 만듭니다.",
    discoveryProvider: "none"
  },
  {
    mode: "browser",
    label: "브라우저를 조작하며 수정",
    description: "Webwright가 실제 페이지를 열고 조작한 evidence를 함께 사용해 draft를 만듭니다.",
    discoveryProvider: "webwright"
  }
];

export function discoveryProviderForUpdateMode(mode: UpdateMode): UpdateDiscoveryProvider {
  return UPDATE_MODE_OPTIONS.find((option) => option.mode === mode)?.discoveryProvider ?? "none";
}

export function updateModeFromDiscoveryProvider(provider: UpdateDiscoveryProvider): UpdateMode {
  return provider === "webwright" ? "browser" : "code-only";
}

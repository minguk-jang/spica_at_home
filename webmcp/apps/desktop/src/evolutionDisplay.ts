export function browserModeLabel(headed: boolean): string {
  return headed ? "브라우저 보기" : "브라우저 숨김";
}

export function evolutionStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    failed: "실패",
    passed: "통과",
    repair_applied: "수정 적용",
    succeeded: "성공",
    waiting_for_repair: "수정 대기"
  };
  return labels[status] ?? status;
}

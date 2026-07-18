---
name: claude-check
description: >
  Codex가 Claude Code 쪽 운영 상태를 점검하는 상호 점검 스킬 (Claude 정본
  「코덱스점검」의 포인터). Claude MCP 프로세스 중복(재연결 좀비)·고아 프로세스·
  RAM/CPU·시크릿 평문 노출·자동 유입 코드(신규 MCP/스킬)를 진단하고 처방을 제시한다.
  사용자가 "클로드 점검", "claude 점검", "클로드 상태 확인", "클로드 무거워",
  "상호 점검", "claude-check"를 언급하면 이 스킬을 사용할 것.
---

# claude-check — Codex → Claude 상호 점검 (포인터)

정본은 Claude 쪽: `~/.claude/skills/코덱스점검/` — **원칙·불가침 목록·처방 레시피는
정본 SKILL.md를 Read하여 그대로 따른다.** 이 문서는 실행 진입점만 제공한다.

## 실행

```bash
PYTHONIOENCODING=utf-8 python "$HOME/.claude/skills/코덱스점검/scripts/check_core.py" --target claude
```

(Windows cmd에서는 `$HOME` 대신 `%USERPROFILE%`)

## 핵심 원칙 요약 (정본과 동일 — 상세는 정본 SKILL.md)

1. **진단은 자동, 수정·삭제·프로세스 종료는 사용자 승인 후** — dry-run(건수·용량 정확) → 승인 → 검증.
2. **불가침**: `~/.claude` 전체(특히 memory·정본 스킬·agents)는 수정·삭제 제안 금지.
   Claude MCP 좀비의 1차 처방은 "Claude 세션 재시작 안내"이며, 프로세스 직접 종료는
   부모 사망 고아 + 알려진 서버 시그니처 이중 확인분만 승인 후.
3. **시크릿 값 미출력** — 위치·키 이름·`SET len=N`만. 노출 발견 시 경고 + rotate 안내.
4. 기준선에 없던 신규 MCP·스킬은 자동 신뢰 금지 — 사용자에게 보고.

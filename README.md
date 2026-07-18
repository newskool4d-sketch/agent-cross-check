# agent-cross-check (코덱스점검)

**한국어** | [English](README.en.md)

Claude Code ↔ OpenAI Codex **상호 운영 점검** 스킬. 한쪽 에이전트가 다른 쪽의 운영
상태를 진단한다 — 자기 자신은 자기를 못 고치기 때문(자기 세션의 좀비 프로세스는
자기 재시작으로만 해소되고, 상대 앱이 꺼져 있어야 잠긴 파일을 정리할 수 있다).

2026-07 Codex 운영 체계 정비(3일, 약 12.8GB 회수)에서 검증된 진단·처방 체계의 스킬화.

## 진단 항목

- **프로세스 계보**: node/bun 프로세스를 소유자(Codex 앱/CLI·Claude·기타)별로 분류,
  세션 잔존 누적·고아 프로세스(부모 사망) 탐지
- **Windows 샌드박스**: `codex-windows-sandbox-setup.exe` 장기 지속 감시 (ACL 폭풍)
- **설정 회귀**: omo codegraph/lsp·훅 다이어트 상태 (자동 업데이트가 설정을 기본값으로
  되돌리는 패턴 대응)
- **저장소 증식**: 텔레메트리 DB 크기, 플러그인 구버전 캐시 잔존
- **보안**: 시크릿 평문 노출 스캔(값은 절대 출력하지 않음 — 위치·길이만),
  광범위 신뢰 목록 재유입, 자동 유입 코드(신규 훅·MCP·마켓 소스) 기준선 diff

## 3대 원칙

1. **진단은 읽기 전용·자동, 수정·삭제는 사용자 승인 후** (dry-run → 승인 → 검증)
2. **정본(SOT) 존중** — 설정은 정본 위치에서만 수정 (예: omo는 `~/.omo/config.jsonc`)
3. **운영 체계 불가침** — 대화 이력·라이브 마켓 소스·hooks/memory/skills 등은
   어떤 처방에도 포함하지 않음

상세는 [SKILL.md](SKILL.md).

## 설치

```bash
# Claude Code 쪽 (정본)
git clone https://github.com/newskool4d-sketch/agent-cross-check "$HOME/.claude/skills/코덱스점검"

# Codex 쪽 (포인터) — pointers/claude-check.SKILL.md를 복사
mkdir -p "$HOME/.codex/skills/claude-check"
cp "$HOME/.claude/skills/코덱스점검/pointers/claude-check.SKILL.md" "$HOME/.codex/skills/claude-check/SKILL.md"
```

요구사항: Python 3.11+ (`tomllib`), `psutil`.

## 사용

- Claude 세션에서 "점검" / "코덱스 점검" → Codex 진단
- Codex 세션에서 "클로드 점검" → Claude 진단
- 수동 실행: `python scripts/check_core.py --target codex|claude|both`

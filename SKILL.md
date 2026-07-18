---
name: 코덱스점검
description: >
  Codex(및 Claude) 운영 체계 상호 점검 스킬. 프로세스 계보(node/bun 소유자 분류)·RAM/CPU·
  sandbox-setup 감시·설정 회귀 감지(codegraph·훅 다이어트)·omo 구버전 캐시·로그 DB 증식·
  고아 프로세스·시크릿 평문 노출·자동 유입 코드(신규 훅/MCP/마켓 소스)를 일괄 진단하고
  처방을 제시한다. 사용자가 "점검", "코덱스 점검", "코덱스 상태 확인", "느려졌어", "무거워",
  "메모리 확인", "성능 저하", "프로세스 확인", "Codex 진단", "상호 점검"을 언급하면 —
  대상을 명시하지 않아도 — 반드시 이 스킬을 사용할 것. Codex 쪽에서 Claude를 점검할 때는
  같은 코어를 --target claude로 실행한다 (Codex 포인터: ~/.codex/skills/claude-check).
---

# 코덱스점검 — Claude ↔ Codex 상호 운영 점검

2026-07 Codex 운영 체계 정비 3일(memory `project-codex-cleanup`)에서 검증된 진단·처방 체계의 스킬화.
**진단은 자동, 수정·삭제는 반드시 사용자 승인 후.**

## 실행

```bash
PYTHONIOENCODING=utf-8 python "$HOME/.claude/skills/코덱스점검/scripts/check_core.py" --target codex
```

(Windows cmd에서는 `$HOME` 대신 `%USERPROFILE%`. 스크립트 내부는 `Path.home()` 기반이라 경로 하드코딩 없음)

- Claude 세션에서 기본 대상은 `codex`. "클로드도"·"전부" 요청 시 `--target both`.
- Codex 세션에서 실행 시 `--target claude` (포인터 스킬이 지정).
- 스크립트는 **읽기 전용**이며 기준선 파일(`state/inventory_*.json`) 갱신 외에 아무것도 쓰지 않는다.

## 리포트 해석과 처방

스크립트가 ⚠️ 항목별로 처방을 함께 출력한다. 에이전트는 리포트를 표로 요약해 보고하고,
처방 실행은 **건별로 승인을 받아** 진행한다. 임계값 근거:

| 신호 | 임계값 | 근거 (실측) |
|---|---|---|
| node 수 | 스레드(git-bash 수) × 6 초과 | 세션당 정상 프로필 ~5개 |
| sandbox-setup | 5분 이상 지속 | 정상 시 수 초~수 분 내 종료 |
| logs_2.sqlite | 300MB | 하루 50~100MB 증식 실측 |
| 앱 연속 구동 | 20시간 | 15.5시간 방치 → node 209개·9.5GB 누적 실측 |
| RAM | 78% ⚠️ / 85% 🔴 | 16GB 머신 기준 |

## 처방 실행 규칙 (3대 원칙)

### 1. 승인 게이트
- 수정·삭제·프로세스 종료는 dry-run(대상·건수·용량 **정확히**) 제시 → 명시 승인 → 실행 → 사후 검증.
- 되돌릴 수 있는 방식(격리 이동) 우선. 영구 삭제는 원본 생존 확인 후.
- 프로세스 종료는 "부모 사망 고아 + 알려진 서버 시그니처" 이중 조건 충족분만 제안.

### 2. 정본(SOT) 존중 — 설정은 정본에서 고친다
| 설정 | 정본 위치 | 주의 |
|---|---|---|
| omo codegraph/lsp 등 | `~/.omo/config.jsonc` | config.toml만 고치면 omo 마이그레이션이 되돌림 (3회 실증) |
| Codex 일반 설정 | `~/.codex/config.toml` | **앱 실행 중 편집 금지** — 종료 시 덮어써짐 |
| `windows.sandbox` | 앱이 강제 | 싸우지 말고 보고만 |
| 훅 on/off | config.toml `[hooks.state]` `enabled` | 해시는 건드리지 않음 |

### 3. 운영 체계 불가침 목록 — 어떤 처방에도 포함 금지
- **Codex**: 현행 플러그인 버전 캐시, `.codex/.tmp/bundled-marketplaces`(라이브 마켓 소스),
  hooks·agents·skills·memories 폴더, `sessions`·`archived_sessions`(대화 이력 — 사용자가 먼저
  요청할 때만 별도 논의), 백업 실행 스크립트(예: backup-to-gdrive.ps1)
- **Claude**: `~/.claude` 전체(기존 보호 규칙), 특히 memory·정본 스킬·agents
- 위험 설정 조합(danger-full-access 등)은 **보고만** — 사용자 의도 설정이며 변경 제안 금지
  (memory `token-strategy-codex-parallel` 의도적 유지 결정 존중)

## 시크릿 취급

- 토큰·키 값은 어떤 출력·리포트·일지에도 **원문 기록 금지** — 위치·키 이름·`SET len=N`만.
- 노출 발견 시: 즉시 경고 + rotate 안내 (로컬 제거는 승인 후, GitHub 웹 revoke는 사용자 몫).
- 신규 훅·MCP·마켓 소스가 기준선에 없던 것이면 **자동 신뢰 금지** — 필요시 `security-vet` 심사 연결.

## 자주 쓰는 처방 레시피 (승인 후)

| 증상 | 처방 |
|---|---|
| 세션 잔존 누적 (node ≫ 스레드×6, 전부 CPU 0%) | Codex 앱 재시작 — 유일하고 확실한 회수 수단 (2회 실증) |
| codegraph/lsp 회귀 | 정본 `~/.omo/config.jsonc` 확인 → Codex **종료 상태**에서 config.toml 재수정 |
| omo 구버전 캐시 | Codex 종료 확인 → 현행 제외 구버전 폴더 삭제 (각 ~430MB) |
| logs_2.sqlite 비대 | Codex 종료 확인 → sqlite+wal+shm 3종 삭제 (자동 재생성) |
| Claude MCP 좀비 (같은 서버 3개+) | Claude 세션 재시작 안내. 고아(부모 사망)는 승인 후 종료 |
| sandbox-setup 장기 지속 | 신뢰 목록 광범위 항목(홈·드라이브 루트) 확인 → 승인 후 해당 항목만 제거 |

## 보고 형식

결론 먼저: `✅ 전 항목 정상` 또는 `⚠️ 조치 검토 N건` → 측정값 표 → 처방 목록(승인 대기 표시).
정기 항목 리마인드가 있으면 함께 (로그 DB 정리 주기 등, memory 참조).

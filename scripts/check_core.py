# -*- coding: utf-8 -*-
"""Claude <-> Codex 상호 운영 점검 진단 코어.

사용:
    python check_core.py --target codex   # Claude가 Codex를 점검 (기본)
    python check_core.py --target claude  # Codex가 Claude를 점검
    python check_core.py --target both

원칙 (SKILL.md 3대 원칙과 동일):
    1. 이 스크립트는 읽기 전용 진단만 한다 — 수정·삭제·프로세스 종료 없음.
    2. 시크릿 값은 절대 출력하지 않는다 — 위치·키 이름·길이만 보고.
    3. 처방은 텍스트 제안일 뿐, 실행은 호출자(에이전트)가 사용자 승인 후 별도로 한다.

2026-07 Codex 운영 체계 정비(3일)에서 검증된 로직의 통합본.
근거 이력: memory project-codex-cleanup.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

try:
    import psutil
except ImportError:
    print("psutil 미설치 — 프로세스 점검 불가 (pip install psutil)")
    sys.exit(1)

sys.stdout.reconfigure(encoding="utf-8")

HOME = Path.home()
CODEX = HOME / ".codex"
CLAUDE = HOME / ".claude"
OMO_SOT = HOME / ".omo" / "config.jsonc"
STATE_DIR = Path(__file__).resolve().parent.parent / "state"

# 임계값 (2026-07 실측 기반)
TH_NODE_PER_SESSION = 6      # 세션당 node 초과 시 경고
TH_SANDBOX_MIN = 5           # sandbox-setup 지속 분
TH_LOGSDB_MB = 300           # logs_2.sqlite 경고 크기 (하루 ~50-100MB 증식 실측)
TH_APP_HOURS = 20            # 앱 연속 구동 경고 (15.5h에 9.5GB 누적 실측)

SECRET_PAT = re.compile(
    r"gho_[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-[A-Za-z0-9_-]{20,}|xox[bap]-[A-Za-z0-9-]{10,}|AIza[A-Za-z0-9_-]{30,}"
)
KEYVAL_PAT = re.compile(r'^\s*([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)\s*=\s*"([^"]{12,})"', re.M)

WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"  ⚠️ {msg}")


def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


# ---------------------------------------------------------------- 프로세스
def snapshot_processes():
    info = {}
    for p in psutil.process_iter(["pid", "ppid", "name", "cmdline", "memory_info", "create_time"]):
        info[p.info["pid"]] = p.info
    return info


def proc_owner(info, pid, depth=8):
    seen = set()
    cur = info.get(pid)
    while cur and depth > 0 and cur["pid"] not in seen:
        seen.add(cur["pid"])
        n = (cur["name"] or "").lower()
        if n in ("codex.exe", "chatgpt.exe"):
            return "CODEX"
        if n == "claude.exe":
            return "CLAUDE"
        cur = info.get(cur["ppid"])
        depth -= 1
    return "OTHER"


def classify_cmd(cmd: str) -> str:
    pats = [
        (r"codegraph", "codegraph"), (r"git-bash|git_bash", "omo-git-bash"),
        (r"lsp-daemon", "omo-lsp"),
        (r"server\.mjs|server\.cjs|server\.bundle", "bundled-doc-server"),
        (r"playwright", "playwright"), (r"npm|npx", "npm/npx"),
        (r"kordoc|obsidian|korean-|telegram|server-pdf", "user-mcp"),
    ]
    for pat, name in pats:
        if re.search(pat, cmd, re.I):
            return name
    m = re.search(r"[\w@.-]+\.(?:js|mjs|cjs|ts|exe)", cmd)
    return (m.group(0)[-35:] if m else "(empty)")


def check_processes(target: str):
    print("\n== 프로세스 ==")
    now = dt.datetime.now()
    info = snapshot_processes()
    alive = set(info)

    owners = defaultdict(Counter)
    mem = defaultdict(lambda: defaultdict(int))
    orphans = []
    sandbox = []
    sessions_hint = 0
    app_age_h = 0.0

    for pid, i in info.items():
        n = (i["name"] or "").lower()
        if n == "codex.exe" and (info.get(i["ppid"], {}).get("name") or "").lower() == "chatgpt.exe":
            app_age_h = max(app_age_h, (now - dt.datetime.fromtimestamp(i["create_time"])).total_seconds() / 3600)
        if n in ("node.exe", "bun.exe"):
            own = proc_owner(info, pid)
            cmd = " ".join(i["cmdline"] or [])
            key = classify_cmd(cmd)
            owners[own][key] += 1
            mem[own][key] += i["memory_info"].rss if i["memory_info"] else 0
            if key == "omo-git-bash":
                sessions_hint += 1
            if i["ppid"] not in alive and re.search(r"mcp|playwright|server", cmd, re.I):
                orphans.append((pid, key))
        elif "sandbox-setup" in n:
            age = (now - dt.datetime.fromtimestamp(i["create_time"])).total_seconds() / 60
            sandbox.append((pid, age))

    for own in sorted(owners, key=lambda o: -sum(mem[o].values())):
        if target != "both" and own.lower() != target and own != "OTHER":
            continue
        total = sum(mem[own].values()) / 1024 / 1024
        print(f"  [{own}] node/bun {sum(owners[own].values())}개, {total:.0f} MB")
        for key, c in owners[own].most_common(6):
            print(f"      {c:3d} x {mem[own][key]/1024/1024:6.0f} MB  {key}")

    if target in ("codex", "both"):
        n_codex = sum(owners["CODEX"].values())
        if sessions_hint and n_codex > sessions_hint * TH_NODE_PER_SESSION:
            warn(f"Codex node {n_codex}개 > 스레드 {sessions_hint}개 × {TH_NODE_PER_SESSION} — 세션 잔존 의심 → 처방: 앱 재시작")
        if app_age_h > TH_APP_HOURS:
            warn(f"Codex 앱 연속 구동 {app_age_h:.0f}시간 — 하루 1회 재시작 수칙 (15.5h 방치 시 9.5GB 누적 실측)")
        for pid, age in sandbox:
            if age > TH_SANDBOX_MIN:
                warn(f"sandbox-setup pid={pid} {age:.0f}분 지속 — 신뢰 목록·홈 ACL 점검 필요")
        if not sandbox:
            ok("sandbox-setup 없음")

    if orphans:
        warn(f"고아 MCP 프로세스 {len(orphans)}개 (부모 사망): " + ", ".join(f"{k}({p})" for p, k in orphans[:6])
             + " → 처방: 승인 후 종료 가능")

    vm = psutil.virtual_memory()
    level = "🔴" if vm.percent > 85 else ("⚠️" if vm.percent > 78 else "✅")
    print(f"  {level} RAM {vm.percent}% 사용, 가용 {vm.available/1024**3:.1f} GB / CPU {psutil.cpu_percent(interval=2)}%")
    if vm.percent > 85:
        WARNINGS.append("RAM 85% 초과")


# ---------------------------------------------------------------- Codex 설정
def check_codex_config():
    print("\n== Codex 설정 무결성 ==")
    cfg_path = CODEX / "config.toml"
    if not (tomllib and cfg_path.exists()):
        warn("config.toml 파싱 불가")
        return {}
    cfg = tomllib.load(cfg_path.open("rb"))

    omo = cfg.get("plugins", {}).get("omo@sisyphuslabs", {}).get("mcp_servers", {})
    cg = omo.get("codegraph", {}).get("enabled")
    lsp = omo.get("lsp", {}).get("enabled")
    if cg is not False:
        warn(f"omo codegraph={cg} — 다이어트 회귀 (omo 업데이트 부작용 패턴) → 처방: 정본 ~/.omo/config.jsonc 확인 후 config 재수정")
    else:
        ok("omo codegraph off 유지")
    if lsp is not False:
        warn(f"omo lsp={lsp} — 다이어트 회귀")

    st = cfg.get("hooks", {}).get("state", {})
    n_off = sum(1 for v in st.values() if v.get("enabled") is False)
    print(f"  훅 항목 {len(st)}개 중 off {n_off}개 (기대: 4+)")
    if n_off < 4:
        warn("훅 다이어트 일부 회귀 의심")

    projects = cfg.get("projects", {})
    print(f"  신뢰 프로젝트 {len(projects)}건")
    if len(projects) > 50:
        warn(f"신뢰 목록 재비대 ({len(projects)}건) — 정리 검토")
    broad = [p for p in projects if p.lower().rstrip("\\") in
             (str(HOME).lower(), "c:", "d:", "g:", r"g:\내 드라이브")]
    if broad:
        warn(f"광범위 신뢰 재유입: {broad} — 샌드박스 ACL 폭풍 위험")

    # 로그 DB
    lp = CODEX / "logs_2.sqlite"
    if lp.exists():
        mb = lp.stat().st_size / 1024 / 1024
        if mb > TH_LOGSDB_MB:
            warn(f"logs_2.sqlite {mb:.0f}MB > {TH_LOGSDB_MB}MB — 처방: Codex 종료 상태에서 삭제(자동 재생성)")
        else:
            ok(f"logs_2.sqlite {mb:.0f}MB")

    # omo 구버전 캐시
    omo_cache = CODEX / "plugins/cache/sisyphuslabs/omo"
    if omo_cache.exists():
        vers = sorted(d.name for d in omo_cache.iterdir() if d.is_dir())
        if len(vers) > 1:
            warn(f"omo 구버전 캐시 잔존: {vers[:-1]} (현행 {vers[-1]}) — 각 ~430MB, 처방: Codex 종료 후 구버전 삭제")
        else:
            ok(f"omo 캐시 단일 버전 ({vers[0] if vers else '없음'})")

    # 위험 설정 조합 — 보고만 (의도적 유지 결정: memory token-strategy 참조)
    combo = f"sandbox_mode={cfg.get('sandbox_mode')} / approval_policy={cfg.get('approval_policy')} / windows.sandbox={cfg.get('windows', {}).get('sandbox')}"
    print(f"  [보안 상태 보고] {combo} — 사용자 의도 설정, 변경 제안 아님")
    return cfg


# ---------------------------------------------------------------- 시크릿 스캔
PLACEHOLDER_PAT = re.compile(r"^(REDACTED|REPLACE_WITH|PLACEHOLDER|CHANGEME|<)", re.I)


def scan_secrets(paths):
    print("\n== 시크릿 평문 스캔 (값 미출력) ==")
    hits: dict[tuple, int] = Counter()   # (파일, 표시라벨) -> 건수
    infos: set[tuple] = set()
    for p in paths:
        if not p.exists() or p.stat().st_size > 5 * 1024 * 1024:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in SECRET_PAT.finditer(text):
            tok = m.group(0)
            prefix = tok[:tok.index("_") + 1] if "_" in tok[:12] else tok[:4]
            hits[(str(p), f"{prefix}... SET len={len(tok)}")] += 1
        for m in KEYVAL_PAT.finditer(text):
            key, val = m.group(1), m.group(2)
            if SECRET_PAT.fullmatch(val) or PLACEHOLDER_PAT.match(val):
                continue  # 토큰은 위에서 보고, 플레이스홀더는 무시
            infos.add((p.name, f"{key} SET len={len(val)}"))
    for (path, label), n in sorted(hits.items()):
        warn(f"토큰 평문 노출: {path} — {label}" + (f" ×{n}" if n > 1 else ""))
    for name, label in sorted(infos):
        print(f"  ℹ️ 평문 자격증명 항목: {name} — {label} (인지된 항목이면 무시)")
    if not hits and not infos:
        ok("신규 토큰 패턴 노출 없음")


def secret_scan_targets(target: str):
    paths = []
    if target in ("codex", "both"):
        paths.append(CODEX / "config.toml")
        b = CODEX / "backups"
        if b.exists():
            paths += [f for f in b.rglob("*.toml") if f.stat().st_size < 1024 * 1024][:20]
            paths += [f for f in b.rglob("*.bak") if f.stat().st_size < 1024 * 1024][:10]
    if target in ("claude", "both"):
        paths += [CLAUDE / "settings.json", HOME / ".claude.json"]
    return paths


# ---------------------------------------------------------------- 유입 코드 diff (기준선)
def inventory_diff(target: str, cfg):
    print("\n== 자동 유입 코드 감지 (기준선 대비) ==")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = STATE_DIR / f"inventory_{target}.json"

    inv = {}
    if target == "codex" and cfg:
        inv = {
            "mcp_servers": sorted(cfg.get("mcp_servers", {})),
            "hooks": sorted(cfg.get("hooks", {}).get("state", {})),
            "marketplaces": {k: v.get("source", "") for k, v in cfg.get("marketplaces", {}).items()},
            "plugins_enabled": sorted(k for k, v in cfg.get("plugins", {}).items() if v.get("enabled")),
        }
    elif target == "claude":
        mcp_file = CLAUDE / "mcp.json"
        servers = []
        if mcp_file.exists():
            try:
                servers = sorted(json.loads(mcp_file.read_text(encoding="utf-8")).get("mcpServers", {}))
            except (json.JSONDecodeError, OSError):
                pass
        skills = sorted(d.name for d in (CLAUDE / "skills").iterdir() if d.is_dir()) if (CLAUDE / "skills").exists() else []
        inv = {"mcp_servers": servers, "skills": skills}

    if state_file.exists():
        try:
            prev = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            prev = {}
        changed = False
        for k in inv:
            cur_set = set(inv[k]) if isinstance(inv[k], list) else set(inv[k].items())
            prev_set = set(prev.get(k, [])) if isinstance(inv[k], list) else set(prev.get(k, {}).items())
            new = cur_set - prev_set
            gone = prev_set - cur_set
            if new:
                changed = True
                warn(f"신규 {k}: {sorted(str(x) for x in new)[:5]} — 자동 신뢰 금지, 필요시 security-vet 심사")
            if gone:
                changed = True
                print(f"  ℹ️ 제거된 {k}: {sorted(str(x) for x in gone)[:5]}")
        if not changed:
            ok("기준선 대비 변화 없음")
    else:
        print("  ℹ️ 기준선 최초 생성")
    state_file.write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- Claude 전용
def check_claude_side():
    print("\n== Claude 상태 ==")
    info = snapshot_processes()
    # 같은 서버 스크립트 중복 = 재연결 좀비 의심
    by_script = Counter()
    for pid, i in info.items():
        if (i["name"] or "").lower() not in ("node.exe", "bun.exe"):
            continue
        if proc_owner(info, pid) != "CLAUDE":
            continue
        cmd = " ".join(i["cmdline"] or [])
        m = re.search(r"[\w@-]+(?:-mcp|mcp[\w-]*|server-pdf|kordoc|obsidian)[\w-]*", cmd, re.I)
        if m:
            by_script[m.group(0).lower()] += 1
    dups = {k: v for k, v in by_script.items() if v > 2}
    if dups:
        warn(f"Claude MCP 중복 스폰 의심(재연결 좀비): {dups} — 처방: Claude 세션 재시작")
    else:
        ok("Claude MCP 중복 스폰 없음")

    proj = CLAUDE / "projects"
    if proj.exists():
        t = sum(f.stat().st_size for f in proj.rglob("*") if f.is_file())
        print(f"  .claude/projects: {t/1024/1024:.0f} MB (세션 기록 + memory — memory 폴더는 불가침)")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["codex", "claude", "both"], default="codex")
    args = ap.parse_args()

    print(f"===== 상호 점검 리포트 ({dt.datetime.now():%Y-%m-%d %H:%M}) — 대상: {args.target} =====")
    print("(읽기 전용 진단 — 어떤 수정·삭제도 하지 않음)")

    cfg = None
    if args.target in ("codex", "both"):
        check_processes("codex")
        cfg = check_codex_config()
        inventory_diff("codex", cfg)
    if args.target in ("claude", "both"):
        if args.target == "both":
            print()
        else:
            check_processes("claude")
        check_claude_side()
        inventory_diff("claude", None)
    scan_secrets(secret_scan_targets(args.target))

    print(f"\n===== 종합: {'⚠️ 조치 검토 ' + str(len(WARNINGS)) + '건' if WARNINGS else '✅ 전 항목 정상'} =====")
    for w in WARNINGS:
        print(f"  - {w}")
    print("(처방 실행은 사용자 승인 후 — 불가침 목록·정본 위치는 SKILL.md 참조)")


if __name__ == "__main__":
    main()

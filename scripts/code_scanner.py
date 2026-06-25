#!/usr/bin/env python3
"""
code_scanner.py
=================
Layer A - estensione: Secret Scanning + Sink Discovery

1. scan_secrets() - Stage 3 di Claude-BugHunter: grep pattern-based su
   tutto il codice decompilato per individuare secret hardcoded.

2. find_component_sinks() - per un dato nome di componente, localizza
   il file .java corrispondente e cerca sink Android pericolosi.

Uso:
    python3 code_scanner.py --decompiled-dir output/<app>/code/decompiled --secrets
    python3 code_scanner.py --decompiled-dir output/<app>/code/decompiled --component "com.example.app.SharedThemeReceiver"
"""

import argparse
import json
import re
import sys
from pathlib import Path


SECRET_PATTERNS = {
    "aws_access_key":      r"AKIA[A-Z0-9]{16}",
    "aws_secret_key":      r"aws_secret_access_key[\s:=]+[A-Za-z0-9/+=]{40}",
    "google_api_key":      r"AIza[A-Za-z0-9_\-]{35}",
    "google_oauth_token":  r"ya29\.[A-Za-z0-9_\-]+",
    "github_pat":          r"gh[ps]_[A-Za-z0-9]{36}",
    "gitlab_pat":          r"glpat-[A-Za-z0-9_\-]{20}",
    "slack_token":         r"xox[pbar]-[A-Za-z0-9\-]+",
    "openai_key":          r"sk-[A-Za-z0-9]{48}",
    "anthropic_key":       r"sk-ant-[A-Za-z0-9_\-]{90,}",
    "stripe_live_key":     r"sk_live_[A-Za-z0-9]{24}",
    "stripe_publishable":  r"pk_live_[A-Za-z0-9]{24}",
    "sendgrid_key":        r"SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}",
    "jwt":                 r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*",
    "client_secret":       r'client_secret["\s:=]+[A-Za-z0-9_\-]{24,}',
    "hardcoded_http_url":  r"http://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}[a-zA-Z0-9./_?=&%\-]*",
}

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ttf", ".so", ".dex"}


def iter_source_files(decompiled_dir: Path):
    for path in decompiled_dir.rglob("*"):
        if path.is_file() and path.suffix not in SKIP_SUFFIXES:
            yield path


def scan_secrets(decompiled_dir: Path, max_findings_per_pattern: int = 20) -> dict:
    findings = {key: [] for key in SECRET_PATTERNS}
    compiled = {key: re.compile(pattern) for key, pattern in SECRET_PATTERNS.items()}

    file_count = 0
    for filepath in iter_source_files(decompiled_dir):
        file_count += 1
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for key, regex in compiled.items():
            if len(findings[key]) >= max_findings_per_pattern:
                continue
            for match in regex.finditer(text):
                if len(findings[key]) >= max_findings_per_pattern:
                    break
                line_no = text.count("\n", 0, match.start()) + 1
                findings[key].append({
                    "file": str(filepath.relative_to(decompiled_dir)),
                    "line": line_no,
                    "match": match.group(0)[:120],
                })

    return {
        "files_scanned": file_count,
        "findings": {k: v for k, v in findings.items() if v},
    }


ANDROID_SINKS = {
    "command_exec":        r"Runtime\.getRuntime\(\)\.exec|ProcessBuilder",
    "webview_load":        r"\.loadUrl\(|\.loadData\(|\.loadDataWithBaseURL\(",
    "webview_js_bridge":   r"addJavascriptInterface",
    "sql_raw_query":       r"\.rawQuery\(|\.execSQL\(",
    "file_read_write":     r"new FileInputStream|new FileOutputStream|openFileOutput|openFileInput",
    "intent_get_extra":    r"getIntent\(\)\.getExtras|getStringExtra|getParcelableExtra|getIntExtra",
    "dynamic_class_load":  r"Class\.forName|DexClassLoader|PathClassLoader",
    "reflection_invoke":   r"\.getMethod\(.*\)\.invoke\(",
    "broadcast_send":      r"sendBroadcast\(|sendOrderedBroadcast\(",
    "external_storage":    r"getExternalStorageDirectory|Environment\.getExternalStorage",
}


def find_component_source_file(decompiled_dir: Path, component_name: str):
    if component_name.startswith("."):
        return None

    relative_path = component_name.replace(".", "/") + ".java"
    candidate = decompiled_dir / "sources" / relative_path
    if candidate.exists():
        return candidate

    simple_name = component_name.rsplit(".", 1)[-1] + ".java"
    matches = list(decompiled_dir.rglob(simple_name))
    return matches[0] if matches else None


def find_component_sinks(decompiled_dir: Path, component_name: str) -> dict:
    source_file = find_component_source_file(decompiled_dir, component_name)

    if source_file is None:
        return {
            "component": component_name,
            "source_file_found": False,
            "note": "File .java non trovato. Possibili cause: nome offuscato, classe "
                    "generata dinamicamente, o componente in libreria esterna (androidx.*).",
            "sinks": {},
        }

    try:
        text = source_file.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {
            "component": component_name,
            "source_file_found": True,
            "source_file": str(source_file.relative_to(decompiled_dir)),
            "error": str(e),
            "sinks": {},
        }

    sinks_found = {}
    for sink_name, pattern in ANDROID_SINKS.items():
        matches = re.findall(pattern, text)
        if matches:
            sinks_found[sink_name] = len(matches)

    return {
        "component": component_name,
        "source_file_found": True,
        "source_file": str(source_file.relative_to(decompiled_dir)),
        "file_size_lines": text.count("\n") + 1,
        "sinks": sinks_found,
    }


def main():
    parser = argparse.ArgumentParser(description="Secret scanning + sink discovery sul codice decompilato")
    parser.add_argument("--decompiled-dir", required=True, type=Path)
    parser.add_argument("--secrets", action="store_true")
    parser.add_argument("--component", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.decompiled_dir.exists():
        print(f"[!] Cartella non trovata: {args.decompiled_dir}", file=sys.stderr)
        sys.exit(1)

    result = {}

    if args.secrets:
        print("[*] Esecuzione secret scanning su tutto il codice decompilato...")
        secrets_result = scan_secrets(args.decompiled_dir)
        result["secrets"] = secrets_result
        print(f"[*] File scansionati: {secrets_result['files_scanned']}")
        if secrets_result["findings"]:
            for pattern_name, findings in secrets_result["findings"].items():
                print(f"\n  [{pattern_name}] {len(findings)} match:")
                for f in findings[:5]:
                    print(f"    {f['file']}:{f['line']} -> {f['match']}")
                if len(findings) > 5:
                    print(f"    ... e altri {len(findings) - 5}")
        else:
            print("[*] Nessun secret pattern trovato.")

    if args.component:
        print(f"\n[*] Ricerca sink per componente: {args.component}")
        sink_result = find_component_sinks(args.decompiled_dir, args.component)
        result["component_sinks"] = sink_result
        if sink_result["source_file_found"]:
            print(f"    File trovato: {sink_result['source_file']} ({sink_result.get('file_size_lines', '?')} righe)")
            if sink_result["sinks"]:
                print("    Sink rilevati:")
                for sink_name, count in sink_result["sinks"].items():
                    print(f"      {sink_name}: {count} occorrenze")
            else:
                print("    Nessun sink Android noto rilevato in questo file.")
        else:
            print(f"    {sink_result['note']}")

    if args.output:
        args.output.write_text(json.dumps(result, indent=2))
        print(f"\n[✓] Risultati salvati in: {args.output}")


if __name__ == "__main__":
    main()

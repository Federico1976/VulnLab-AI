import json, sys, zipfile
from pathlib import Path

PATTERNS = {
    "flutter": ["flutter_assets", "libflutter.so", "libapp.so", "io/flutter", "FlutterActivity", "FlutterEngine"],
    "flutter_channels": ["MethodChannel", "EventChannel", "BasicMessageChannel", "BinaryMessenger", "DartExecutor"],
    "react_native": ["assets/index.android.bundle", "com/facebook/react"],
    "firebase": ["com/google/firebase", "FirebaseMessagingService"],
    "webview": ["android/webkit/WebView", "loadUrl(", "evaluateJavascript(", "addJavascriptInterface("],
    "kotlin": ["kotlinx/coroutines", "kotlin.Metadata"],
}

def hit_in_zip(apk):
    hits = {}
    try:
        with zipfile.ZipFile(apk) as z:
            names = z.namelist()
            joined = "\n".join(names)
            for k, pats in PATTERNS.items():
                m = [p for p in pats if p.lower() in joined.lower()]
                if m:
                    hits.setdefault(k, []).extend([f"{apk}:{x}" for x in m])
    except Exception:
        pass
    return hits

def hit_in_files(root):
    hits = {}
    if not root.exists():
        return hits
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        sp = str(f)
        for k, pats in PATTERNS.items():
            if any(p.lower() in sp.lower() for p in pats):
                hits.setdefault(k, []).append(sp)
        if f.suffix.lower() in {".java", ".kt", ".xml", ".json"}:
            try:
                txt = f.read_text(errors="ignore")[:200000]
            except Exception:
                continue
            for k, pats in PATTERNS.items():
                if any(p in txt for p in pats):
                    hits.setdefault(k, []).append(sp)
    return hits

def merge(a, b):
    for k, v in b.items():
        a.setdefault(k, []).extend(v)
    return a

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m runtime_fingerprint.runtime_fingerprint_v2 output/<target_dir> [apk_or_apk_dir]")
        sys.exit(1)

    target = Path(sys.argv[1])
    apk_input = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    hits = {}
    merge(hits, hit_in_files(target / "code" / "decompiled"))

    if apk_input:
        apks = list(apk_input.glob("*.apk")) if apk_input.is_dir() else [apk_input]
        for apk in apks:
            merge(hits, hit_in_zip(apk))

    hits = {k: sorted(set(v)) for k, v in hits.items()}

    primary = "native"
    if "flutter" in hits:
        primary = "flutter"
    elif "react_native" in hits:
        primary = "react_native"

    fp = {
        "primary_runtime": primary,
        "runtimes": [k for k in ["flutter", "react_native", "kotlin"] if k in hits],
        "bridges": (
            ["flutter_method_channel_candidate"] if "flutter" in hits else []
        ) + (
            ["react_native_bridge"] if "react_native" in hits else []
        ),
        "surfaces": (
            ["dart_to_native_bridge_surface"] if "flutter" in hits else []
        ) + (
            ["js_to_native_bridge_surface"] if "react_native" in hits else []
        ) + (
            ["webview_surface"] if "webview" in hits else []
        ),
        "hit_counts": {k: len(v) for k, v in hits.items()},
        "evidence": {k: v[:30] for k, v in hits.items()},
        "guardrail": "Runtime fingerprint only. Not vulnerability evidence."
    }

    out = target / "runtime_fingerprint_v2.json"
    out.write_text(json.dumps(fp, indent=2), encoding="utf-8")
    print("[+] written", out)
    print(json.dumps({k: fp[k] for k in ["primary_runtime","runtimes","bridges","surfaces","hit_counts"]}, indent=2))

if __name__ == "__main__":
    main()

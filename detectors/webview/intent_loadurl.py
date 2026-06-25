from reasoning_agent import joern_bridge

DETECTOR_ID = "APK-WEBVIEW-INTENT-LOADURL-001"

def _dedup(items):
    seen = set()
    out = []
    for x in items:
        key = tuple(sorted(x.items()))
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out

def analyze(cpg_path: str) -> dict:
    lines = [
        f'importCpg("{cpg_path}")',
        'println("###RESULT_START###")',

        'val intentSources = cpg.call.name("getStringExtra|getStringArrayExtra|getIntExtra|getLongExtra|getBooleanExtra|getFloatExtra|getDoubleExtra|getData|getDataString|getExtras|getBundleExtra|getSerializableExtra|getParcelableExtra").l',
        'val webviewSinks = cpg.call.name("loadUrl|loadData|loadDataWithBaseURL|evaluateJavascript|addJavascriptInterface").l',

        'println("TOTAL_INTENT_SOURCES=" + intentSources.size)',
        'println("TOTAL_WEBVIEW_SINKS=" + webviewSinks.size)',

        'val methodsWithBoth = intentSources.method.fullName.toSet.intersect(webviewSinks.method.fullName.toSet)',
        'println("METHODS_WITH_BOTH=" + methodsWithBoth.size)',
        'methodsWithBoth.foreach(m => println("BOTH|" + m))',

        'intentSources.filter(c => methodsWithBoth.contains(c.method.fullName)).foreach(c => println("SOURCE|" + c.method.fullName + "|" + c.lineNumber.getOrElse(-1) + "|" + c.code))',
        'webviewSinks.filter(c => methodsWithBoth.contains(c.method.fullName)).foreach(c => println("SINK|" + c.method.fullName + "|" + c.lineNumber.getOrElse(-1) + "|" + c.code))',

        'println("###RESULT_END###")',
        ':quit',
    ]

    raw = joern_bridge._run_joern(lines, timeout=240)
    section = raw.split("###RESULT_START###")[-1].split("###RESULT_END###")[0]

    sources, sinks, both = [], [], []

    for line in section.splitlines():
        line = line.strip()
        if "SOURCE|" in line:
            line = line[line.index("SOURCE|"):]
        elif "SINK|" in line:
            line = line[line.index("SINK|"):]
        elif "BOTH|" in line:
            line = line[line.index("BOTH|"):]

        if line.startswith("SOURCE|"):
            _, method, lineno, code = line.split("|", 3)
            sources.append({"method": method, "line": lineno, "code": code})
        elif line.startswith("SINK|"):
            _, method, lineno, code = line.split("|", 3)
            sinks.append({"method": method, "line": lineno, "code": code})
        elif line.startswith("BOTH|"):
            both.append(line.split("|", 1)[1])

    sources = _dedup(sources)
    sinks = _dedup(sinks)
    both = sorted(set(both))

    findings = []
    for method in both:
        method_sources = [s for s in sources if s["method"] == method]
        method_sinks = [s for s in sinks if s["method"] == method]

        findings.append({
            "id": DETECTOR_ID,
            "title": "Intent-controlled data may reach WebView sink",
            "category": "webview",
            "severity": "high",
            "confidence": "medium",
            "masvs": ["MASVS-PLATFORM", "MASVS-CODE"],
            "maswe": ["MASWE-WEBVIEW", "MASWE-IPC", "MASWE-PLATFORM"],
            "method": method,
            "sources": method_sources,
            "sinks": method_sinks,
            "risk": "Potential externally controlled Intent/deep-link data reaches a WebView sink.",
            "next_validation": [
                "Correlate method class with AndroidManifest exported/activity/deeplink status.",
                "Extract exact Intent extra name feeding the WebView.",
                "Check allowlist/scheme validation before loadUrl.",
                "Validate dynamically with adb am start only inside authorized bounty scope."
            ],
            "false_positive_checks": [
                "Activity not exported and not externally reachable.",
                "Intent value is internally generated only.",
                "Strict domain allowlist exists before WebView load.",
                "Only hardcoded trusted URL reaches the sink."
            ]
        })

    return {
        "detector": DETECTOR_ID,
        "methods_with_both": both,
        "sources": sources,
        "sinks": sinks,
        "findings": findings,
        "raw_tail": raw[-2000:]
    }

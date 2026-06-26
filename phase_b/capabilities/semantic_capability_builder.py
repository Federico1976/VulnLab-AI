#!/usr/bin/env python3
import json
import sys
from pathlib import Path


CAPABILITY_RULES = [
    {
        "capability": "IntentLaunchCapability",
        "category": "ipc_intent",
        "keywords": ["Intent", "startActivity", "startActivityForResult", "setAction", "setData", "setDataAndType", "putExtra", "createChooser"],
        "security_questions": [
            "Can attacker-controlled data influence intent action, data, extras, flags, or target component?",
            "Does the intent cross an app/process boundary?",
            "Is there permission, package, component, or scheme restriction?"
        ],
    },
    {
        "capability": "WebViewNavigationCapability",
        "category": "webview_navigation",
        "keywords": ["WebView", "loadUrl", "shouldStartLoadWith", "shouldOverrideUrlLoading", "url"],
        "security_questions": [
            "Can attacker-controlled data influence a WebView URL?",
            "Is the URL restricted by scheme/host allowlist?",
            "Can JavaScript interfaces or privileged WebView settings amplify impact?"
        ],
    },
    {
        "capability": "FileAccessCapability",
        "category": "filesystem",
        "keywords": ["File", "FileInputStream", "FileOutputStream", "read", "write", "uri", "path", "RNFS", "createTempFile"],
        "security_questions": [
            "Can attacker-controlled data influence file path or URI?",
            "Is path canonicalized and constrained to an allowed directory?",
            "Does this expose private app files or external storage data?"
        ],
    },
    {
        "capability": "FileProviderCapability",
        "category": "filesystem_ipc",
        "keywords": ["FileProvider", "getUriForFile", "content://", "android.intent.extra.STREAM"],
        "security_questions": [
            "Can attacker-controlled file paths be wrapped into content URIs?",
            "Is the FileProvider path configuration restrictive?",
            "Can another app receive unintended file access?"
        ],
    },
    {
        "capability": "ExternalInputCapability",
        "category": "source_controllability",
        "keywords": ["getString", "getBoolean", "getDouble", "ReadableMap", "Bundle", "Intent", "getData", "getInitialURL", "hasKey"],
        "security_questions": [
            "Is this source controlled by JS, user input, intent data, deeplink, remote config, or external app?",
            "Is the value trusted by construction or attacker-influenced?",
            "Does the source cross a trust boundary?"
        ],
    },
    {
        "capability": "SanitizerOrGuardCapability",
        "category": "validation",
        "keywords": ["hasKey", "startsWith", "toLowerCase", "parse", "validate", "sanitize", "check", "verify", "permission", "allow"],
        "security_questions": [
            "Does this guard validate the dangerous value or only check presence/type?",
            "Is validation semantic and complete?",
            "Can alternate encoding, nullability, scheme, host, or path form bypass it?"
        ],
    },
    {
        "capability": "CryptoOrHashCapability",
        "category": "crypto_hash",
        "keywords": ["MD5", "SHA-1", "SHA-256", "MessageDigest", "hash"],
        "security_questions": [
            "Is hashing used for security or only functional integrity?",
            "Is a weak algorithm security-relevant?",
            "Can attacker-controlled input influence security-sensitive verification?"
        ],
    },
    {
        "capability": "NetworkOrUploadCapability",
        "category": "network_upload",
        "keywords": ["upload", "uploadFiles", "createFormData", "http", "https", "URL"],
        "security_questions": [
            "Can attacker-controlled file or data be uploaded?",
            "Is destination controlled or trusted?",
            "Does this expose sensitive local data?"
        ],
    },
    {
        "capability": "DocumentPickerCapability",
        "category": "document_provider",
        "keywords": ["OPEN_DOCUMENT_TREE", "pickDirectory", "INITIAL_URI", "DocumentPicker"],
        "security_questions": [
            "Does the user explicitly select the document/tree?",
            "Can initial URI or picker behavior be attacker-influenced?",
            "Does selected access persist or escape intended scope?"
        ],
    },
]


def flatten_strings(obj):
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(flatten_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(flatten_strings(v))
    elif isinstance(obj, str):
        out.append(obj)
    return out


def score_rule(text, rule):
    hits = []
    lower = text.lower()

    for kw in rule["keywords"]:
        if kw.lower() in lower:
            hits.append(kw)

    score = min(100, len(hits) * 20)
    return score, hits


def infer_capabilities(request):
    text = " ".join(flatten_strings({
        "hints": request.get("hints", {}),
        "queries": request.get("queries", []),
        "task_type": request.get("task_type"),
        "query_goal": request.get("query_goal"),
    }))

    capabilities = []

    for rule in CAPABILITY_RULES:
        score, hits = score_rule(text, rule)
        if score <= 0:
            continue

        confidence = "high" if score >= 60 else "medium" if score >= 40 else "low"

        capabilities.append({
            "capability_type": rule["capability"],
            "category": rule["category"],
            "confidence": confidence,
            "score": score,
            "matched_keywords": hits,
            "security_questions": rule["security_questions"],
        })

    capabilities.sort(key=lambda c: c["score"], reverse=True)
    return capabilities


def build_capability_object(request):
    capabilities = infer_capabilities(request)

    return {
        "capability_object_id": f"SC-{request['joern_request_id']}",
        "joern_request_id": request["joern_request_id"],
        "joern_task_id": request["joern_task_id"],
        "hypothesis_id": request["hypothesis_id"],
        "story_id": request["story_id"],
        "research_object_id": request["research_object_id"],
        "candidate_id": request["candidate_id"],
        "task_type": request["task_type"],
        "query_goal": request["query_goal"],
        "capability_count": len(capabilities),
        "capabilities": capabilities,
        "capability_summary": {
            "has_external_input": any(c["capability_type"] == "ExternalInputCapability" for c in capabilities),
            "has_intent_launch": any(c["capability_type"] == "IntentLaunchCapability" for c in capabilities),
            "has_webview_navigation": any(c["capability_type"] == "WebViewNavigationCapability" for c in capabilities),
            "has_file_access": any(c["capability_type"] == "FileAccessCapability" for c in capabilities),
            "has_file_provider": any(c["capability_type"] == "FileProviderCapability" for c in capabilities),
            "has_sanitizer_or_guard": any(c["capability_type"] == "SanitizerOrGuardCapability" for c in capabilities),
            "has_crypto_or_hash": any(c["capability_type"] == "CryptoOrHashCapability" for c in capabilities),
            "has_network_or_upload": any(c["capability_type"] == "NetworkOrUploadCapability" for c in capabilities),
            "has_document_picker": any(c["capability_type"] == "DocumentPickerCapability" for c in capabilities),
        },
        "status": "candidate_capabilities_from_query_context",
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "requires_joern_result_confirmation": True,
            "requires_proof_evaluator": True,
        },
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.capabilities.semantic_capability_builder <joern_query_requests.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())
    requests = data.get("joern_query_requests", [])

    objects = [build_capability_object(r) for r in requests]

    all_caps = [c for o in objects for c in o["capabilities"]]

    summary = {}
    for c in all_caps:
        summary[c["capability_type"]] = summary.get(c["capability_type"], 0) + 1

    output = {
        "schema": "vulnlab.semantic_capabilities.v1",
        "input_schema": data.get("schema"),
        "capability_object_count": len(objects),
        "capability_count": len(all_caps),
        "summary": summary,
        "capability_objects": objects,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "semantic_capabilities_are_not_findings": True,
            "requires_execution_evidence": True,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "capability_objects": len(objects),
        "capabilities": len(all_caps),
        "summary": summary,
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()

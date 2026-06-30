import json, re, sys, urllib.request
from pathlib import Path
from html import unescape
from phase_c.knowledge_sources.source_collector_base import make_raw_item, write_raw_item

INDEX_URL = "https://source.android.com/docs/security/bulletin"

KEYWORD_MAP = {
    "intent": ["intent", "activity", "service", "receiver", "permission", "privilege escalation"],
    "file": ["file", "path", "content uri", "provider", "directory traversal"],
    "webview": ["webview", "javascript", "origin", "url", "browser"],
    "storage": ["credential", "token", "keystore", "storage", "backup", "log"]
}

RELEVANCE_MAP = {
    "intent": ["external_app_to_app_internal_boundary","exported_component","intent_extra","intent_action","privileged_action_execution","missing_permission_check"],
    "file": ["content_uri_to_filesystem_boundary","fileprovider_paths","content_uri_grant","file_read","path_scope_validation","unauthorized_file_read"],
    "webview": ["web_content_to_native_code_boundary","javascript_interface","webview_add_javascript_interface","webview_evaluate_javascript","missing_origin_check","native_bridge_invocation"],
    "storage": ["app_internal_storage_to_attacker_boundary","token_read","credential_use","local_storage","backup_exposure","sensitive_data_exfiltration"]
}

FAMILY = {
    "intent": "exported_component_intent_injection",
    "file": "fileprovider_exposure",
    "webview": "webview_js_bridge_origin_confusion",
    "storage": "token_storage_exposure"
}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent":"VulnLab-AI-PhaseC/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def clean_html(s):
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S|re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S|re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def find_bulletin_links(html, limit):
    links = sorted(set(re.findall(r'href="([^"]*/docs/security/bulletin/\d{4}/\d{4}-\d{2}-\d{2})"', html)))
    full = []
    for u in links:
        if u.startswith("http"):
            full.append(u)
        else:
            full.append("https://source.android.com" + u)
    return full[:limit]

def classify(text):
    low = text.lower()
    tags = []
    for tag, words in KEYWORD_MAP.items():
        if any(w in low for w in words):
            tags.append(tag)
    if not tags:
        tags = ["intent"]
    relevance = []
    for t in tags:
        relevance += RELEVANCE_MAP[t]
    family = FAMILY.get(tags[0], "android_platform_security_pattern")
    return sorted(set(tags)), sorted(set(relevance)), family

def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("phase_c/knowledge_ingestion/raw_items")
    state_path = Path("phase_c/knowledge_sources/state/android_bulletin_seen.json")
    seen = set(json.load(open(state_path)) if state_path.exists() else [])

    html = fetch(INDEX_URL)
    links = find_bulletin_links(html, limit)
    written = []

    for url in links:
        if url in seen:
            continue
        page = fetch(url)
        text = clean_html(page)
        title_m = re.search(r"Android Security Bulletin[^<\n]*", page)
        title = clean_html(title_m.group(0)) if title_m else f"Android Security Bulletin {url.rsplit('/',1)[-1]}"
        tags, relevance, family = classify(text[:12000])
        source_id = "RAW-ANDROID-BULLETIN-" + url.rsplit("/",1)[-1].upper()

        item = make_raw_item(
            source_id=source_id,
            source=url,
            source_type="android_security_bulletin",
            title=title,
            summary=text[:1800],
            ecosystem="android",
            references=[{"type":"android_security_bulletin","value":url}],
            known_security_relevance=relevance,
            expected_case_family=family,
            human_reviewed=False
        )
        p = write_raw_item(item, out_dir)
        written.append(str(p))
        seen.add(url)

    state_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(sorted(seen), open(state_path,"w"), indent=2)

    print(json.dumps({"status":"ok","collector":"android_bulletin_real","seen":len(seen),"written":len(written),"outputs":written}, indent=2))

if __name__ == "__main__":
    main()

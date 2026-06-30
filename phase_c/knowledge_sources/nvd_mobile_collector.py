import json, sys, urllib.parse, urllib.request
from pathlib import Path
from phase_c.knowledge_sources.source_collector_base import make_raw_item, write_raw_item

BASE="https://services.nvd.nist.gov/rest/json/cves/2.0"

KEYWORDS=["android","webview","intent","content provider","fileprovider","deeplink","mobile"]

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"VulnLab-AI-PhaseC/1.0"})
    with urllib.request.urlopen(req,timeout=45) as r:
        return json.loads(r.read().decode())

def relevance_from_text(t):
    low=t.lower()
    rel=[]
    fam="android_platform_security_pattern"
    if any(x in low for x in ["webview","javascript"]):
        rel+=["web_content_to_native_code_boundary","javascript_interface","webview_add_javascript_interface","missing_origin_check","native_bridge_invocation"]; fam="webview_js_bridge_origin_confusion"
    if any(x in low for x in ["intent","activity","receiver","service"]):
        rel+=["external_app_to_app_internal_boundary","exported_component","intent_extra","intent_action","privileged_action_execution","missing_permission_check"]; fam="exported_component_intent_injection"
    if any(x in low for x in ["file","provider","content uri","path"]):
        rel+=["content_uri_to_filesystem_boundary","fileprovider_paths","content_uri_grant","file_read","path_scope_validation","unauthorized_file_read"]; fam="fileprovider_exposure"
    if any(x in low for x in ["token","credential","storage","backup","log"]):
        rel+=["app_internal_storage_to_attacker_boundary","token_read","credential_use","local_storage","backup_exposure","sensitive_data_exfiltration"]; fam="token_storage_exposure"
    return sorted(set(rel)), fam

def main():
    out=Path(sys.argv[1]) if len(sys.argv)>1 else Path("phase_c/knowledge_ingestion/raw_items")
    max_per_kw=int(sys.argv[2]) if len(sys.argv)>2 else 5
    state=Path("phase_c/knowledge_sources/state/nvd_seen.json")
    seen=set(json.load(open(state)) if state.exists() else [])
    written=[]

    for kw in KEYWORDS:
        qs=urllib.parse.urlencode({"keywordSearch":kw,"resultsPerPage":max_per_kw,"startIndex":0,"noRejected":""})
        try:
            data=get(BASE+"?"+qs)
        except Exception as e:
            print(json.dumps({"warning":"nvd_request_failed","keyword":kw,"error":str(e)}))
            continue
        for v in data.get("vulnerabilities",[]):
            cve=v.get("cve",{})
            cveid=cve.get("id")
            if not cveid or cveid in seen: continue
            desc=" ".join(d.get("value","") for d in cve.get("descriptions",[]) if d.get("lang")=="en")
            rel,fam=relevance_from_text(desc)
            if not rel: continue
            refs=[{"type":"nvd_cve","value":f"https://nvd.nist.gov/vuln/detail/{cveid}"}]
            raw_refs = cve.get("references", [])
            if isinstance(raw_refs, dict):
                raw_refs = raw_refs.get("referenceData", [])
            if isinstance(raw_refs, list):
                for r in raw_refs[:5]:
                    if isinstance(r, dict) and r.get("url"):
                        refs.append({"type":"reference","value":r["url"]})
            item=make_raw_item(
                source_id="RAW-NVD-"+cveid,
                source="nvd_cve_api_2_0",
                source_type="nvd_cve",
                title=cveid,
                summary=desc[:1800],
                ecosystem="android",
                references=refs,
                known_security_relevance=rel,
                expected_case_family=fam,
                human_reviewed=False
            )
            p=write_raw_item(item,out); written.append(str(p)); seen.add(cveid)

    state.parent.mkdir(parents=True,exist_ok=True)
    json.dump(sorted(seen),open(state,"w"),indent=2)
    print(json.dumps({"status":"ok","collector":"nvd_mobile","seen":len(seen),"written":len(written)},indent=2))

if __name__=="__main__":
    main()

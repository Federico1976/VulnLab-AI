import json, sys, urllib.request
from pathlib import Path
from phase_c.knowledge_sources.source_collector_base import make_raw_item, write_raw_item

API="https://api.osv.dev/v1/query"

def post(payload):
    data=json.dumps(payload).encode()
    req=urllib.request.Request(API,data=data,headers={"Content-Type":"application/json","User-Agent":"VulnLab-AI-PhaseC/1.0"})
    with urllib.request.urlopen(req,timeout=45) as r:
        return json.loads(r.read().decode())

def main():
    if len(sys.argv)!=4:
        raise SystemExit("usage: python3 -m phase_c.knowledge_sources.osv_dependency_collector <ecosystem> <package> <raw_out>")
    ecosystem, package, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    data=post({"package":{"name":package,"ecosystem":ecosystem}})
    written=[]
    for vuln in data.get("vulns",[])[:20]:
        vid=vuln.get("id")
        summary=(vuln.get("summary") or vuln.get("details") or "")[:1800]
        low=summary.lower()
        rel=["dependency_vulnerability"]
        fam="dependency_security_advisory"
        if any(x in low for x in ["android","intent","webview","content provider","file"]):
            rel+=["external_app_to_app_internal_boundary","privileged_action_execution"]
            fam="android_dependency_relevant"
        item=make_raw_item(
            source_id="RAW-OSV-"+vid,
            source="osv_api",
            source_type="osv",
            title=vid + " " + (vuln.get("summary") or ""),
            summary=summary,
            ecosystem="android",
            references=[{"type":"osv","value":"https://osv.dev/vulnerability/"+vid}],
            known_security_relevance=rel,
            expected_case_family=fam,
            human_reviewed=False
        )
        p=write_raw_item(item,out); written.append(str(p))
    print(json.dumps({"status":"ok","collector":"osv_dependency","package":package,"written":len(written)},indent=2))
if __name__=="__main__":
    main()

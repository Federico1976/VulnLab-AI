import json, glob, sys
from pathlib import Path
from phase_c.knowledge_memory.vulnerability_case_validator import validate_vulnerability_case

AUTOMATED = {"nvd_cve", "android_security_bulletin", "osv", "github_advisory"}

def review(path):
    case=json.load(open(path))
    v=validate_vulnerability_case(case)
    src=case.get("identity",{}).get("source_quality","unknown")
    fam=case.get("identity",{}).get("vulnerability_family","unknown")
    seed_unknowns=[]
    causal=case.get("causal_shape",{})
    for k in ["trust_boundary","sensitive_operation","security_effect","exploit_primitive"]:
        val=causal.get(k,{})
        if isinstance(val,dict):
            s=json.dumps(val).lower()
            if "unknown" in s:
                seed_unknowns.append(k)

    requires_llm = src in AUTOMATED or bool(seed_unknowns)
    status = "promotion_ready" if v["status"]=="valid" and src not in AUTOMATED and not seed_unknowns else "needs_review"

    return {
        "path": path,
        "case_id": case.get("identity",{}).get("case_id"),
        "source_quality": src,
        "family": fam,
        "validator_status": v["status"],
        "validator_errors": v["errors"],
        "seed_unknowns": seed_unknowns,
        "review_status": status,
        "requires_llm_competence": requires_llm,
        "recommended_competences": [
            "extract_root_cause",
            "extract_trust_boundary",
            "extract_counterevidence",
            "extract_dynamic_validation_idea"
        ] if requires_llm else []
    }

def main():
    in_dir=sys.argv[1] if len(sys.argv)>1 else "phase_c/knowledge_ingestion/vulnerability_case_candidates"
    out=sys.argv[2] if len(sys.argv)>2 else "phase_c/knowledge_ingestion/candidate_review_report.json"
    records=[review(p) for p in sorted(glob.glob(f"{in_dir}/*.json"))]
    report={
        "status":"ok",
        "schema":"vulnlab.candidate_review_report.v1",
        "summary":{
            "candidates":len(records),
            "promotion_ready":sum(1 for r in records if r["review_status"]=="promotion_ready"),
            "needs_review":sum(1 for r in records if r["review_status"]=="needs_review"),
            "requires_llm_competence":sum(1 for r in records if r["requires_llm_competence"])
        },
        "records":records
    }
    Path(out).parent.mkdir(parents=True,exist_ok=True)
    json.dump(report,open(out,"w"),indent=2,ensure_ascii=False)
    print(json.dumps(report["summary"],indent=2))
if __name__=="__main__":
    main()

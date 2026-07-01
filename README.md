# VulnLab-AI 2.0

**VulnLab-AI 2.0** is a local, defensive, responsible-disclosure Android APK research agent.

It is designed for open-source APKs, authorized bug bounty targets, and responsible security research.

It is not a scanner. It is a cognitive APK research agent that learns abstract investigation strategies from evidence, episodes, proof gaps, counter-evidence, and validation outcomes.


<img width="1050" height="195" alt="image" src="https://github.com/user-attachments/assets/d3582ada-27c4-4da6-9132-e800210a97f9" />


## Cognitive Pipeline

```text
Evidence Story
↓
Semantic Story Normalizer
↓
Continuous Knowledge Trainer
↓
Pattern Distillation Engine
↓
Strategy Memory v2
↓
Hypothesis Prioritizer
↓
Hypothesis Object
↓
Universal Investigation Planner v2
↓
Reasoning Executor v1
↓
Phase C Readiness Gate
Core Guardrails
candidate_only=true
finding_allowed=false
report_allowed=false
target_specific_detectors_allowed=false
learns_findings=false
learns_cves=false
LLM/Ollama Role

LLM/Ollama is integrated as a reasoning and triage layer over structured evidence.

It does not create findings.
It does not override guardrails.
It helps reason over Evidence Story, Semantic Story, Strategy Memory, Hypothesis Priorities, Investigation Plans, and Reasoning Executor decisions.

Phase C Final Readiness

VulnLab-AI 2.0 completed Phase C cognitive readiness:

global_score=1.0
ready_apk_count=5/5
all_ready_for_heterogeneous_apk_campaign=true


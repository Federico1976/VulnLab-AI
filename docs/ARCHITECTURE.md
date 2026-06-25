# VulnLab-AI Architecture

## Objective

VulnLab-AI is designed as a universal Android APK Hunting Agent.

The system is built around runtime modeling, semantic evidence, reachability reasoning, dynamic validation planning, and responsible disclosure preparation.

## Architecture v1.0

```text
APK
 ↓
Characterization
 ↓
Runtime Family Engine
 ↓
Runtime Role Ranking
 ↓
Runtime Artifact Layer
 ↓
Runtime Artifact Confidence
 ↓
Capability Provider Engine
 ↓
Semantic Objects
 ↓
Evidence Graph v5
 ↓
Runtime Ontology v4
 ↓
Reachability Candidate
 ↓
Dynamic Validation Plan
 ↓
Responsible Disclosure Candidate
Runtime Families

Validated:

Android Native
Kotlin / Compose
React Native
Flutter
Hybrid Web
Unity

Pending:

Xamarin / .NET MAUI
NativeScript
Design Rules
No target-specific detectors.
No vulnerability claim from static signal alone.
Every candidate must preserve evidence.
Reachability must be separated from discovery.
Dynamic validation is mandatory before disclosure.
The LLM must reason over structured graphs, not raw code dumps.
Phase B Direction

Phase B will focus on the intelligence layer:

Dynamic Confidence Learning
Causal Reachability
Graph-based Reasoning Engine

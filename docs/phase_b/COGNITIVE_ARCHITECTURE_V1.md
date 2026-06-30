# VulnLab-AI Cognitive Architecture v1

## Goal

Build a trainable APK hunting research agent that reasons like a security researcher.

The agent must not be a scanner and must not rely on raw LLM code reading.

It must reason over structured evidence, causal proof, validation feedback and research memory.

## Eight Cognitive Layers

1. Runtime Understanding
2. Evidence Understanding
3. Research Memory
4. Hypothesis Generator
5. Investigation Planner
6. Knowledge Engine
7. Reasoning Loop
8. Learning Memory

## Core Loop

ResearchCase
→ CognitiveState
→ Reasoning Decision
→ Proof Request
→ Proof Evaluation
→ State Update
→ Learning Feedback
→ Memory Update

## Non-Negotiable Rules

- Candidate evidence only.
- No vulnerability claim without causal reachability and dynamic validation.
- No target-specific detector logic.
- Every false positive becomes learning memory.
- Every confirmed proof becomes learning memory.
- Every APK must improve the universal agent.
- LLMs reason over structured cases, not raw code dumps.

## Current Implemented Blocks

- Evidence Case Normalizer
- Research Case Layer
- Knowledge Memory v1
- Dynamic Confidence Learner
- Cognitive State Controller
- Investigation Planner
- Reasoning Loop v1
- Causal Proof Request Builder
- Causal Proof Evaluator
- Cognitive State Updater
- Learning Feedback Committer

## Next Blocks

1. Research Memory Store
2. Investigation Episode Recorder
3. Knowledge Pattern Scoring
4. Causal Proof Adapter for Joern outputs
5. Comparative APK Cognitive Campaign
6. LLM Reasoning Adapter
7. Dynamic Validation Result Integrator
8. Long-term Learning Memory

# VulnLab-AI – Universal Android APK Hunting Agent

## Missione

Costruire un agente universale per APK hunting difensivo/responsible disclosure.

Non è uno scanner.

Principi:
- candidate evidence only
- nessuna vulnerabilità senza reachability + dynamic validation
- Context Engineering > detector
- Source → Propagation → Reachability → Sink → Exploitability → Dynamic Validation → Responsible Disclosure
- ogni APK amplia l'universalità del motore

## Stato completato

### Core già validato

- APK Characterization Engine
- Universal Pipeline Selector
- Guaranteed Decompiled Workspace
- Runtime Fingerprint 2.0
- Universal Reachability Engine
- Universal EntryPoint Correlator
- Activity/Navigation Correlator
- Next Hop Extractor
- Universal Path Pruning Engine
- Flutter Surface Hunt
- Universal Runtime Artifact Extractor
- Semantic Runtime KG
- Confidence Engine
- Evidence Graph v2
- Universal Coverage Matrix
- Reasoning API v1

## APK usati come milestone

- Tesla: React Native Bridge → Native sink
- Vienna: Kotlin/Compose/WebView + deeplink correlation
- SEEK: Deeplink → Activity → Intent → Uri Router → next-hop extraction
- Linktree: RN + SDK ecosystem + Universal Path Pruning Engine
- Mashops: Flutter runtime reale + PigeonRPC + PluginRegistration + causal evidence stories

## Qualità attuale

Mashops produce evidence stories causali pronte per reachability.

Gli altri APK producono ancora segnali/capability, ma non abbastanza semantic objects forti per reasoning sicuro.

Questo è corretto: il sistema non sovrastima evidenze deboli.

## Prossimo passo

Costruire bridge semantici:

- RN Bridge → Semantic Story
- WebView/DeepLink → Semantic Story
- Activity/Intent Router → Semantic Story

Obiettivo:
portare Tesla, Vienna, SEEK e Linktree da raw_signals_only a strong_semantic_objects / causal_evidence_stories_ready_for_reachability.

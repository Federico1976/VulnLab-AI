from typing import Dict, Any, List

from intelligence_layer.causal_reachability.models import (
    CausalReachabilityGraph,
    CausalEdge,
)


class CausalReachabilityBuilder:
    """
    Builds a causal reachability graph from normalized candidate evidence.

    This is not yet Joern-proven reachability.
    It creates a structured reasoning graph that Phase B can later upgrade
    using Joern call graph, data flow, and propagation graph proofs.
    """

    def build(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        graph = CausalReachabilityGraph(
            candidate_id=candidate.get("candidate_id", candidate.get("id", "unknown")),
            apk_id=candidate.get("apk_id", candidate.get("target", "unknown")),
            runtime_family=candidate.get("runtime_family", "unknown"),
            entrypoints=self._list(candidate, "entrypoints"),
            sources=self._list(candidate, "sources"),
            sinks=self._list(candidate, "sinks"),
        )

        self._add_entrypoint_to_source_edges(graph)
        self._add_source_to_sink_edges(graph, candidate)
        self._score_proof_level(graph, candidate)

        return graph.to_dict()

    def _list(self, candidate: Dict[str, Any], key: str) -> List[str]:
        value = candidate.get(key, [])
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, str):
                    result.append(item)
                elif isinstance(item, dict):
                    result.append(
                        item.get("method")
                        or item.get("name")
                        or item.get("value")
                        or str(item)
                    )
                else:
                    result.append(str(item))
            return result
        return [str(value)]

    def _add_entrypoint_to_source_edges(self, graph: CausalReachabilityGraph) -> None:
        for entry in graph.entrypoints:
            for source in graph.sources:
                graph.edges.append(CausalEdge(
                    source=entry,
                    target=source,
                    edge_type="entrypoint_to_source",
                    evidence="candidate_correlation",
                    confidence=0.55,
                ))
                graph.reasoning.append(
                    f"Entrypoint {entry} is correlated with source {source}."
                )

    def _add_source_to_sink_edges(
        self,
        graph: CausalReachabilityGraph,
        candidate: Dict[str, Any]
    ) -> None:
        evidence_type = candidate.get("evidence_type", "unknown")
        reachability = candidate.get("reachability_result", candidate.get("reachability", "unknown"))

        for source in graph.sources:
            for sink in graph.sinks:
                if evidence_type == "cpg_local_proven" or reachability == "proven":
                    evidence = "local_cpg_or_proven_reachability"
                    confidence = 0.90
                elif evidence_type == "source_text_fallback":
                    evidence = "source_text_fallback_flow"
                    confidence = 0.62
                else:
                    evidence = "predicted_static_correlation"
                    confidence = 0.40

                graph.edges.append(CausalEdge(
                    source=source,
                    target=sink,
                    edge_type="source_to_sink",
                    evidence=evidence,
                    confidence=confidence,
                ))
                graph.reasoning.append(
                    f"Source {source} is connected to sink {sink} using {evidence}."
                )

    def _score_proof_level(
        self,
        graph: CausalReachabilityGraph,
        candidate: Dict[str, Any]
    ) -> None:
        if not graph.entrypoints:
            graph.proof_level = "no_entrypoint"
            graph.reasoning.append("No entrypoint evidence is available.")
            return

        if not graph.sources or not graph.sinks:
            graph.proof_level = "incomplete"
            graph.reasoning.append("Missing source or sink evidence.")
            return

        evidence_type = candidate.get("evidence_type", "unknown")
        reachability = candidate.get("reachability_result", candidate.get("reachability", "unknown"))

        if evidence_type == "cpg_local_proven" and reachability == "proven":
            graph.proof_level = "proven_local_causal"
        elif evidence_type == "cpg_local_proven":
            graph.proof_level = "strong_causal"
        elif evidence_type == "source_text_fallback":
            graph.proof_level = "fallback_causal_candidate"
        else:
            graph.proof_level = "predicted_only"

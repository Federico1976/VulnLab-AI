from typing import Dict, Any, List


class EntrypointQualityScorer:
    """
    Classifies recovered entrypoint hints.

    Critical distinction:
    - entrypoint: where attacker/runtime input enters
    - sink_action: what the app later does internally
    - runtime_context: helper/context methods
    """

    def score_entrypoints(self, entrypoints: List[str]) -> Dict[str, Any]:
        scored = []

        for ep in entrypoints:
            scored.append(self._score_one(ep))

        external = [x for x in scored if x["classification"] == "external_entrypoint"]
        bridge = [x for x in scored if x["classification"] == "bridge_entrypoint"]
        lifecycle = [x for x in scored if x["classification"] == "lifecycle_callback"]
        weak = [x for x in scored if x["classification"] == "weak_hint"]
        context = [x for x in scored if x["classification"] == "runtime_context"]
        sink_action = [x for x in scored if x["classification"] == "sink_action"]
        discard = [x for x in scored if x["classification"] == "discard"]

        real_entrypoints = (
            [x["entrypoint"] for x in external]
            + [x["entrypoint"] for x in bridge]
            + [x["entrypoint"] for x in lifecycle]
        )

        return {
            "scored_entrypoints": scored,
            "real_entrypoints": real_entrypoints,
            "external_entrypoints": [x["entrypoint"] for x in external],
            "bridge_entrypoints": [x["entrypoint"] for x in bridge],
            "lifecycle_callbacks": [x["entrypoint"] for x in lifecycle],
            "weak_hints": [x["entrypoint"] for x in weak],
            "runtime_context": [x["entrypoint"] for x in context],
            "sink_actions": [x["entrypoint"] for x in sink_action],
            "discarded": [x["entrypoint"] for x in discard],
            "quality_summary": {
                "external": len(external),
                "bridge": len(bridge),
                "lifecycle": len(lifecycle),
                "weak": len(weak),
                "runtime_context": len(context),
                "sink_action": len(sink_action),
                "discard": len(discard),
            }
        }

    def _score_one(self, ep: str) -> Dict[str, Any]:
        text = ep.strip()
        low = text.lower()

        score = 0.0
        reasons = []
        classification = "discard"


        # Concrete React Native bridge methods recovered as Module.method / Manager.method.
        if (
            (
                ".module." in low
                or "module." in low
                or "manager." in low
                or "rnfsmanager." in low
                or "rnfileviewermodule." in low
                or "addtocalendarmodule." in low
                or "rncwebviewmodule." in low
            )
            and not any(x in low for x in [
                "getcurrentactivity",
                "startactivity",
                "resolveactivity",
                "getpackagemanager",
                "currentactivity"
            ])
        ):
            return {
                "entrypoint": ep,
                "score": 0.90,
                "classification": "bridge_entrypoint",
                "reasons": ["concrete recovered React Native bridge method"]
            }

        # Generic Android framework classes are not app entrypoints.
        if low in {"android.app.activity", "android.app.service"}:
            return {
                "entrypoint": ep,
                "score": 0.0,
                "classification": "discard",
                "reasons": ["generic Android framework class"]
            }

        # Sink/action contexts must be detected before Activity heuristics.
        if any(x in low for x in [
            "startactivity",
            "resolveactivity",
            "loadurl(",
            "fileinputstream",
            "urifromfile",
            "uri.fromfile",
            "setdataandtype",
        ]):
            return {
                "entrypoint": ep,
                "score": 0.20,
                "classification": "sink_action",
                "reasons": ["runtime action or sink context, not an entrypoint"]
            }

        # React Native bridge entrypoints.
        if "reactmethod" in low and len(text) > len("@ReactMethod"):
            score = 0.90
            classification = "bridge_entrypoint"
            reasons.append("specific React Native bridge method")

        elif text == "@ReactMethod":
            score = 0.35
            classification = "weak_hint"
            reasons.append("ReactMethod annotation without method name")

        # Android external components.
        elif (
            (
                text.endswith("Activity")
                or text.endswith("Receiver")
                or text.endswith("Service")
            )
            and "." in text
            and not any(x in low for x in [
                "getcurrentactivity",
                "currentactivity",
                "startactivity",
                "resolveactivity"
            ])
        ):
            score = 0.80
            classification = "external_entrypoint"
            reasons.append("specific Android component class")

        # Lifecycle/callback entrypoints.
        elif any(x in low for x in [
            "oncreate(",
            "onnewintent",
            "shouldoverrideurlloading",
            "onreceive(",
            "onstartcommand(",
        ]):
            score = 0.75
            classification = "lifecycle_callback"
            reasons.append("Android lifecycle or callback method")

        # Runtime context helpers.
        elif any(x in low for x in [
            "currentactivity",
            "getcurrentactivity",
            "reactapplicationcontext",
            "reactcontext",
        ]):
            score = 0.25
            classification = "runtime_context"
            reasons.append("runtime context helper, not external entrypoint")

        elif text.startswith("."):
            score = 0.0
            classification = "discard"
            reasons.append("incomplete fragment")

        else:
            score = 0.0
            classification = "discard"
            reasons.append("not an entrypoint")

        return {
            "entrypoint": ep,
            "score": round(score, 4),
            "classification": classification,
            "reasons": reasons
        }

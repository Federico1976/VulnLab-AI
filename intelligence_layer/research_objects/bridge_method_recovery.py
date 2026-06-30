import re
from typing import Dict, Any, List


class BridgeMethodRecovery:
    """
    Recovers concrete React Native bridge methods from raw candidate evidence.

    Goal:
    @ReactMethod + method signature -> Module.method as bridge_entrypoint
    """

    METHOD_PATTERNS = [
        r"@ReactMethod\s+(?:public|private|protected)?\s*(?:void|boolean|int|double|float|String|Promise|ReadableMap|ReadableArray)?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"@ReactMethod[^A-Za-z0-9_]+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"ReactMethod\s+([A-Za-z0-9_.$]+)",
        r"method['\"]?\s*:\s*['\"]([^'\"]+)['\"]",
        r"\"method\"\s*:\s*\"([^\"]+)\"",
    ]

    CLASS_PATTERNS = [
        r"class['\"]?\s*:\s*['\"]([^'\"]+)['\"]",
        r"\"class\"\s*:\s*\"([^\"]+)\"",
        r"([A-Za-z0-9_.$]+Module)",
        r"([A-Za-z0-9_.$]+Manager)",
    ]

    BAD_METHODS = {
        "getCurrentActivity",
        "currentActivity",
        "startActivity",
        "resolveActivity",
        "waitForActivity",
        "getSystemService",
        "registerReceiver",
        "queryIntentService",
    }

    def recover(self, research_object: Dict[str, Any]) -> Dict[str, Any]:
        obj = dict(research_object)

        blob = self._blob(obj)
        classes = self._recover_classes(blob)
        methods = self._recover_methods(blob)

        bridge_entrypoints = []

        for method in methods:
            if method in self.BAD_METHODS:
                continue

            if classes:
                for cls in classes:
                    bridge_entrypoints.append(f"{cls}.{method}")
            else:
                bridge_entrypoints.append(f"ReactMethod.{method}")

        existing = obj.get("merged_entrypoints", [])
        merged = []

        for item in existing + bridge_entrypoints:
            if item not in merged:
                merged.append(item)

        obj["merged_entrypoints"] = merged
        obj["bridge_method_recovery"] = {
            "classes": classes,
            "methods": methods,
            "bridge_entrypoints": bridge_entrypoints,
        }

        return obj

    def _blob(self, obj: Dict[str, Any]) -> str:
        return str(obj)

    def _recover_methods(self, blob: str) -> List[str]:
        methods = []

        for pattern in self.METHOD_PATTERNS:
            for match in re.findall(pattern, blob):
                method = match.strip()
                if method and method not in methods:
                    methods.append(method)

        return methods

    def _recover_classes(self, blob: str) -> List[str]:
        classes = []

        for pattern in self.CLASS_PATTERNS:
            for match in re.findall(pattern, blob):
                cls = match.strip()
                if cls and cls not in classes:
                    classes.append(cls)

        return classes[:5]

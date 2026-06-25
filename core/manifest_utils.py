import json
from pathlib import Path

COMPONENT_KEYS = {
    "activities": "activity",
    "services": "service",
    "receivers": "receiver",
    "providers": "provider",
}

def load_manifest(output_dir):
    return json.loads(Path(output_dir, "manifest.json").read_text())

def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from _walk(x)

def all_components(manifest):
    out = []
    for d in _walk(manifest):
        for key, ctype in COMPONENT_KEYS.items():
            if key in d and isinstance(d[key], list):
                for item in d[key]:
                    if isinstance(item, dict) and item.get("name"):
                        x = dict(item)
                        x["_component_type"] = ctype
                        x["_section"] = key
                        out.append(x)
    return out

def normalize_class_name(name):
    if not name:
        return ""
    name = name.replace("$", ".")
    # inner class -> outer class fallback
    if "." in name:
        parts = name.split(".")
        # keep full; caller may also compare outer
    return name

def outer_class(name):
    name = normalize_class_name(name)
    parts = name.split(".")
    if parts and len(parts[-1]) == 1:
        return ".".join(parts[:-1])
    return name

def find_component_by_class(manifest, class_name):
    target = normalize_class_name(class_name)
    target_outer = outer_class(target)

    for c in all_components(manifest):
        name = normalize_class_name(c.get("name", ""))
        if name == target or name == target_outer:
            return c
    return None

def is_externally_reachable(component):
    if not component:
        return False
    if component.get("exported") is True:
        return True
    if component.get("intent_filters"):
        return True
    return False

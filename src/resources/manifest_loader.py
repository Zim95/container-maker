"""
Manifest loader — read a k8s resource template from src/resources/manifests/, substitute
${VAR} placeholders, and return the parsed document(s) as dicts ready for the kubernetes client.

Pilot for the "define resources as YAML the code picks up" pattern (starting with NetworkPolicies):
the resource *shape* lives in a reviewable/auditable YAML file, the runtime values are injected
here. The client accepts a dict body, so no V1* object construction is needed.
"""
import os
from typing import Dict, List, Any

import yaml

MANIFESTS_DIR: str = os.path.join(os.path.dirname(__file__), "manifests")


def render_manifests(manifest_file: str, substitutions: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Load a (possibly multi-document) YAML template from the manifests dir, replace every
    ${KEY} with substitutions[KEY], and return the parsed documents (empty docs dropped).
    """
    path: str = os.path.join(MANIFESTS_DIR, manifest_file)
    with open(path, "r") as f:
        text: str = f.read()
    for key, value in substitutions.items():
        text = text.replace("${" + key + "}", str(value))
    return [doc for doc in yaml.safe_load_all(text) if doc]

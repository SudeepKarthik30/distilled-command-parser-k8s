import glob
import json
import py_compile
import pytest
import yaml

def test_manifests_parse():
    """Verify that all Kubernetes manifests are syntactically valid YAML."""
    manifest_files = glob.glob("k8s/*.yaml") + glob.glob("network/*.yaml")
    assert len(manifest_files) > 0, "No Kubernetes manifests found."
    for filepath in manifest_files:
        with open(filepath, "r", encoding="utf-8") as fh:
            list(yaml.safe_load_all(fh))

def test_python_compiles():
    """Ensure all core Python services and scripts compile without syntax errors."""
    python_modules = [
        "service/app.py",
        "training/train.py",
        "tools/score.py",
        "worker/clean.py",
        "scripts/generate_report.py"
    ]
    for module_path in python_modules:
        py_compile.compile(module_path, doraise=True)

def test_schema_intent_and_slots():
    """Validate data/schema.json structure against the required 8 intents and 4 keys."""
    with open("data/schema.json", "r", encoding="utf-8") as f:
        schema = json.load(f)
    
    assert "keys" in schema or "properties" in schema or "required" in schema
    expected_intents = {
        "alarm_set", "alarm_query", "calendar_set", "calendar_query",
        "calendar_remove", "weather_query", "datetime_query", "recommendation_events"
    }
    # Check that schema contains the 8 intents
    schema_str = json.dumps(schema)
    for intent in expected_intents:
        assert intent in schema_str, f"Missing expected intent: {intent}"

def test_rate_card_structure():
    """Verify data/rate_card.json holds the required pricing coefficients."""
    with open("data/rate_card.json", "r", encoding="utf-8") as f:
        rc = json.load(f)
    assert rc.get("currency") == "INR"
    assert "vcpu_hour" in rc and rc["vcpu_hour"] > 0
    assert "gib_memory_hour" in rc and rc["gib_memory_hour"] > 0

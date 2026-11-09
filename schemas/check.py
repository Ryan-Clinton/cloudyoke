#!/usr/bin/env python3
"""Check the reading schema against its examples: every file in examples/good must pass, every one in
examples/bad must fail. Needs the jsonschema package.

    python schemas/check.py
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

HERE = Path(__file__).parent
schema = json.loads((HERE / "reading.schema.json").read_text())
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema, format_checker=FormatChecker())

failures = 0
for expect, folder in (("pass", "good"), ("fail", "bad")):
    for path in sorted((HERE / "examples" / folder).glob("*.json")):
        errors = list(validator.iter_errors(json.loads(path.read_text())))
        ok = not errors if expect == "pass" else bool(errors)
        failures += not ok
        detail = "" if ok or expect == "fail" else f": {errors[0].message}"
        print(f"{'ok  ' if ok else 'FAIL'} {folder}/{path.name} should {expect}{detail}")
sys.exit(1 if failures else 0)

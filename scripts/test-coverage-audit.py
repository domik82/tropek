#!/usr/bin/env python3
"""One-time audit: map integration tests to Pact/Schemathesis coverage.

Reads:
  - ui/pacts/tropek-ui-tropek-api.json (Pact interactions, optional)
  - api/openapi.json (list of all endpoints — schemathesis coverage)
  - api/tests/**/test_*.py (existing integration tests)

Produces:
  - reports/test-audit.md — Markdown table: each integration test → coverage class
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACT_FILE = REPO_ROOT / 'ui' / 'pacts' / 'tropek-ui-tropek-api.json'
OPENAPI_FILE = REPO_ROOT / 'api' / 'openapi.json'
API_TESTS_DIR = REPO_ROOT / 'api' / 'tests'
REPORT_OUT = REPO_ROOT / 'reports' / 'test-audit.md'


@dataclass
class TestFunction:
    file: Path
    name: str
    docstring: str
    markers: list[str]
    body_text: str


def extract_pact_endpoints(pact_path: Path) -> set[tuple[str, str]]:
    """Return {(METHOD, path)} covered by Pact interactions."""
    if not pact_path.exists():
        return set()
    data = json.loads(pact_path.read_text())
    endpoints: set[tuple[str, str]] = set()
    for interaction in data.get('interactions', []):
        request = interaction.get('request', {})
        method = request.get('method', '').upper()
        path = request.get('path', '')
        if method and path:
            endpoints.add((method, path))
    return endpoints


def extract_all_endpoints(openapi_path: Path) -> set[tuple[str, str]]:
    """Return {(METHOD, path)} from the OpenAPI spec — Schemathesis coverage."""
    data = json.loads(openapi_path.read_text())
    endpoints: set[tuple[str, str]] = set()
    for path, methods in data.get('paths', {}).items():
        for method in methods:
            if method.lower() in {'get', 'post', 'put', 'patch', 'delete'}:
                endpoints.add((method.upper(), path))
    return endpoints


def find_test_functions(tests_dir: Path) -> list[TestFunction]:
    """Walk tests/ and collect every test function with docstring and markers."""
    functions: list[TestFunction] = []
    for test_file in tests_dir.rglob('test_*.py'):
        if 'schemathesis' in test_file.parts or 'contracts' in test_file.parts:
            continue
        try:
            tree = ast.parse(test_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not node.name.startswith('test_'):
                continue
            markers = [
                decorator.attr
                for decorator in node.decorator_list
                if isinstance(decorator, ast.Attribute)
                and isinstance(decorator.value, ast.Attribute)
                and getattr(decorator.value, 'attr', None) == 'mark'
            ]
            functions.append(
                TestFunction(
                    file=test_file.relative_to(REPO_ROOT),
                    name=node.name,
                    docstring=ast.get_docstring(node) or '',
                    markers=markers,
                    body_text=ast.unparse(node),
                )
            )
    return functions


def classify(test_function: TestFunction, pact_endpoints: set[tuple[str, str]]) -> str:
    """Heuristic classification. Final decision is human, this is a starting point."""
    body_lower = test_function.body_text.lower()
    for method, path in pact_endpoints:
        path_fragment = path.split('{')[0].rstrip('/')
        if path_fragment and path_fragment in body_lower and method.lower() in body_lower:
            return 'covered-by-pact'
    if 'status_code' in body_lower and 'assert' in body_lower and 'response' in body_lower:
        return 'api-shape-check (candidate for schemathesis coverage)'
    if 'session.add' in body_lower or 'select(' in body_lower:
        return 'business-logic / db-state (keep)'
    return 'unclassified (human review)'


def main() -> None:
    pact_endpoints = extract_pact_endpoints(PACT_FILE)
    api_endpoints = extract_all_endpoints(OPENAPI_FILE)
    functions = find_test_functions(API_TESTS_DIR)

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        '# Test Coverage Audit',
        '',
        f'- Pact interactions: {len(pact_endpoints)}'
        + ('' if pact_endpoints else ' (no pact file — Phase 2 not yet landed)'),
        f'- OpenAPI endpoints: {len(api_endpoints)} '
        '(all covered by schemathesis unless excluded)',
        f'- Integration test functions inspected: {len(functions)}',
        '',
        '| File | Test | Classification | Docstring (first line) |',
        '| --- | --- | --- | --- |',
    ]
    for test_function in sorted(functions, key=lambda item: (str(item.file), item.name)):
        doc_first_line = (
            test_function.docstring.split('\n', 1)[0] if test_function.docstring else ''
        )
        classification = classify(test_function, pact_endpoints)
        lines.append(
            f'| `{test_function.file}` | `{test_function.name}` | '
            f'{classification} | {doc_first_line} |'
        )
    lines.extend(
        [
            '',
            '## Legend',
            '',
            '- **covered-by-pact**: Pact verifies the same endpoint shape. '
            'Candidate for removal if the integration test adds no business-logic '
            'value beyond shape.',
            '- **api-shape-check (candidate for schemathesis coverage)**: Asserts '
            'status codes or response shapes. Likely already covered by '
            'Schemathesis — candidate for removal.',
            '- **business-logic / db-state (keep)**: Exercises DB state, '
            'multi-step sequences, or computed values. Keep.',
            '- **unclassified (human review)**: Could not be auto-classified. '
            'Requires reading the test to decide.',
            '',
            '## Next step',
            '',
            'A human reviews every row, deletes the rows marked for removal, and '
            'expands the "keep" rows where business-logic assertions are thin.',
        ]
    )

    REPORT_OUT.write_text('\n'.join(lines) + '\n')
    print(f'wrote {REPORT_OUT.relative_to(REPO_ROOT)}')


if __name__ == '__main__':
    main()

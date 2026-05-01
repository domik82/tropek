"""Unit tests for asset meta timeline group hierarchy builder (§7.4)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from tropek.modules.asset_meta.timeline.tree_builder import (
    build_group_entry,
    build_groups_wire,
    collect_distinct_paths,
    compute_children_map,
    encode_path_as_group_id,
    expand_with_synthetic_ancestors,
    sort_groups_deterministically,
)
from tropek.modules.asset_meta.timeline.types import ClippedSpan

_WINDOW_START = datetime(2026, 4, 1, tzinfo=UTC)
_WINDOW_END = datetime(2026, 4, 30, tzinfo=UTC)


def make_clipped(path: list[str] | None = None, **kwargs: object) -> ClippedSpan:
    defaults: dict = {
        'source': 'cicd',
        'path': path or ['app'],
        'value': '1.0',
        'start': _WINDOW_START,
        'end': _WINDOW_END,
        'className': 'meta-span',
    }
    defaults.update(kwargs)
    return ClippedSpan(**defaults)


# ---------------------------------------------------------------------------
# encode_path_as_group_id
# ---------------------------------------------------------------------------


class TestEncodePathAsGroupId:
    def test_simple_single_segment(self) -> None:
        assert encode_path_as_group_id(('app',)) == '["app"]'

    def test_multi_segment(self) -> None:
        assert encode_path_as_group_id(('app-A', 'pkg-1', 'alpha')) == '["app-A","pkg-1","alpha"]'

    def test_path_with_single_quote_is_json_safe(self) -> None:
        encoded = encode_path_as_group_id(("it's",))
        # Must be valid JSON and decode back correctly
        decoded = json.loads(encoded)
        assert decoded == ["it's"]

    def test_path_with_slash_preserved(self) -> None:
        encoded = encode_path_as_group_id(('a/b',))
        decoded = json.loads(encoded)
        assert decoded == ['a/b']

    def test_path_with_colon_preserved(self) -> None:
        encoded = encode_path_as_group_id(('k8s:pod',))
        decoded = json.loads(encoded)
        assert decoded == ['k8s:pod']

    def test_unicode_preserved_not_escaped(self) -> None:
        encoded = encode_path_as_group_id(('café',))
        # ensure_ascii=False means the character appears literally, not as \\uXXXX
        assert 'café' in encoded
        assert json.loads(encoded) == ['café']

    def test_round_trip_restores_original_list(self) -> None:
        path = ('app-A', 'pkg-1', 'alpha')
        assert json.loads(encode_path_as_group_id(path)) == list(path)


# ---------------------------------------------------------------------------
# collect_distinct_paths
# ---------------------------------------------------------------------------


class TestCollectDistinctPaths:
    def test_empty_spans_returns_empty_set(self) -> None:
        assert collect_distinct_paths([]) == set()

    def test_duplicate_paths_deduplicated(self) -> None:
        spans = [
            make_clipped(path=['app', 'svc']),
            make_clipped(path=['app', 'svc']),
        ]
        result = collect_distinct_paths(spans)
        assert result == {('app', 'svc')}

    def test_different_paths_all_preserved(self) -> None:
        spans = [
            make_clipped(path=['app']),
            make_clipped(path=['db']),
            make_clipped(path=['cache']),
        ]
        result = collect_distinct_paths(spans)
        assert result == {('app',), ('db',), ('cache',)}

    def test_mixed_depths(self) -> None:
        spans = [
            make_clipped(path=['app']),
            make_clipped(path=['app', 'svc']),
        ]
        result = collect_distinct_paths(spans)
        assert result == {('app',), ('app', 'svc')}


# ---------------------------------------------------------------------------
# expand_with_synthetic_ancestors
# ---------------------------------------------------------------------------


class TestExpandWithSyntheticAncestors:
    def test_leaf_only_produces_all_ancestor_prefixes(self) -> None:
        leaf_paths: set[tuple[str, ...]] = {('a', 'b', 'c')}
        result = expand_with_synthetic_ancestors(leaf_paths)
        assert result == {('a',), ('a', 'b'), ('a', 'b', 'c')}

    def test_already_expanded_input_is_idempotent(self) -> None:
        already_expanded: set[tuple[str, ...]] = {('a',), ('a', 'b'), ('a', 'b', 'c')}
        result = expand_with_synthetic_ancestors(already_expanded)
        assert result == already_expanded

    def test_empty_input_returns_empty_set(self) -> None:
        assert expand_with_synthetic_ancestors(set()) == set()

    def test_two_sibling_leaves_share_ancestor(self) -> None:
        sibling_paths: set[tuple[str, ...]] = {('a', 'x'), ('a', 'y')}
        result = expand_with_synthetic_ancestors(sibling_paths)
        assert ('a',) in result
        assert ('a', 'x') in result
        assert ('a', 'y') in result

    def test_single_root_stays_as_root(self) -> None:
        root_paths: set[tuple[str, ...]] = {('app',)}
        result = expand_with_synthetic_ancestors(root_paths)
        assert result == {('app',)}


# ---------------------------------------------------------------------------
# compute_children_map
# ---------------------------------------------------------------------------


class TestComputeChildrenMap:
    def test_parent_with_two_children_both_listed(self) -> None:
        paths: set[tuple[str, ...]] = {('a',), ('a', 'x'), ('a', 'y')}
        children_map = compute_children_map(paths)
        assert set(children_map[('a',)]) == {('a', 'x'), ('a', 'y')}

    def test_leaf_node_absent_as_key(self) -> None:
        paths: set[tuple[str, ...]] = {('a',), ('a', 'x')}
        children_map = compute_children_map(paths)
        assert ('a', 'x') not in children_map

    def test_root_path_parent_not_emitted(self) -> None:
        # A root path has no parent — the empty tuple should not appear as a key
        paths: set[tuple[str, ...]] = {('app',)}
        children_map = compute_children_map(paths)
        assert () not in children_map

    def test_empty_paths_returns_empty_map(self) -> None:
        assert dict(compute_children_map(set())) == {}

    def test_three_level_hierarchy(self) -> None:
        paths: set[tuple[str, ...]] = {('a',), ('a', 'b'), ('a', 'b', 'c')}
        children_map = compute_children_map(paths)
        assert children_map[('a',)] == [('a', 'b')]
        assert children_map[('a', 'b')] == [('a', 'b', 'c')]
        assert ('a', 'b', 'c') not in children_map


# ---------------------------------------------------------------------------
# sort_groups_deterministically
# ---------------------------------------------------------------------------


class TestSortGroupsDeterministically:
    def test_same_input_different_orderings_produce_identical_output(self) -> None:
        paths_set_a: set[tuple[str, ...]] = {('b',), ('a',), ('a', 'z'), ('a', 'y')}
        paths_set_b: set[tuple[str, ...]] = {('a', 'y'), ('b',), ('a', 'z'), ('a',)}
        assert sort_groups_deterministically(paths_set_a) == sort_groups_deterministically(paths_set_b)

    def test_roots_before_depth_two(self) -> None:
        paths: set[tuple[str, ...]] = {('a',), ('b',), ('a', 'x'), ('b', 'y')}
        result = sort_groups_deterministically(paths)
        root_indices = [i for i, path in enumerate(result) if len(path) == 1]
        leaf_indices = [i for i, path in enumerate(result) if len(path) == 2]
        assert max(root_indices) < min(leaf_indices)

    def test_lexicographic_within_same_depth(self) -> None:
        paths: set[tuple[str, ...]] = {('z',), ('a',), ('m',)}
        result = sort_groups_deterministically(paths)
        assert result == [('a',), ('m',), ('z',)]

    def test_empty_input_returns_empty_list(self) -> None:
        assert sort_groups_deterministically(set()) == []


# ---------------------------------------------------------------------------
# build_group_entry
# ---------------------------------------------------------------------------


class TestBuildGroupEntry:
    def test_leaf_entry_has_only_id_and_content(self) -> None:
        children_map: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
        entry = build_group_entry(('app',), children_map)
        assert set(entry.keys()) == {'id', 'content'}
        assert entry['id'] == encode_path_as_group_id(('app',))
        assert entry['content'] == 'app'

    def test_parent_entry_has_nested_groups_and_show_nested(self) -> None:
        children_map: dict[tuple[str, ...], list[tuple[str, ...]]] = {
            ('app',): [('app', 'svc')],
        }
        entry = build_group_entry(('app',), children_map)
        assert 'nestedGroups' in entry
        assert 'showNested' in entry
        assert entry['showNested'] is False

    def test_nested_groups_contains_encoded_child_ids(self) -> None:
        children_map: dict[tuple[str, ...], list[tuple[str, ...]]] = {
            ('app',): [('app', 'svc'), ('app', 'db')],
        }
        entry = build_group_entry(('app',), children_map)
        expected_ids = sorted(
            [
                encode_path_as_group_id(('app', 'svc')),
                encode_path_as_group_id(('app', 'db')),
            ]
        )
        assert entry['nestedGroups'] == expected_ids

    def test_nested_groups_are_sorted_deterministically(self) -> None:
        children_map: dict[tuple[str, ...], list[tuple[str, ...]]] = {
            ('app',): [('app', 'z'), ('app', 'a'), ('app', 'm')],
        }
        entry = build_group_entry(('app',), children_map)
        child_ids = entry['nestedGroups']
        assert child_ids == sorted(child_ids)

    def test_content_is_last_path_segment(self) -> None:
        children_map: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
        entry = build_group_entry(('app', 'pkg', 'alpha'), children_map)
        assert entry['content'] == 'alpha'


# ---------------------------------------------------------------------------
# build_groups_wire — end-to-end
# ---------------------------------------------------------------------------


class TestBuildGroupsWire:
    """End-to-end tests using a fixture with paths at mixed depths."""

    def _make_fixture_spans(self) -> list[ClippedSpan]:
        return [
            make_clipped(path=['app-A']),
            make_clipped(path=['app-A', 'plug-1', 'alpha']),
            make_clipped(path=['cpu-cores']),
        ]

    def _groups_by_id(self, groups: list[dict]) -> dict[str, dict]:
        return {group['id']: group for group in groups}

    def test_synthetic_intermediate_ancestor_emitted(self) -> None:
        groups = build_groups_wire(self._make_fixture_spans())
        group_ids = {group['id'] for group in groups}
        synthetic_id = encode_path_as_group_id(('app-A', 'plug-1'))
        assert synthetic_id in group_ids

    def test_app_a_has_plug_1_in_nested_groups(self) -> None:
        groups = build_groups_wire(self._make_fixture_spans())
        by_id = self._groups_by_id(groups)
        app_a_id = encode_path_as_group_id(('app-A',))
        plug_1_id = encode_path_as_group_id(('app-A', 'plug-1'))
        assert plug_1_id in by_id[app_a_id]['nestedGroups']

    def test_plug_1_has_alpha_in_nested_groups(self) -> None:
        groups = build_groups_wire(self._make_fixture_spans())
        by_id = self._groups_by_id(groups)
        plug_1_id = encode_path_as_group_id(('app-A', 'plug-1'))
        alpha_id = encode_path_as_group_id(('app-A', 'plug-1', 'alpha'))
        assert alpha_id in by_id[plug_1_id]['nestedGroups']

    def test_cpu_cores_has_no_nested_groups(self) -> None:
        groups = build_groups_wire(self._make_fixture_spans())
        by_id = self._groups_by_id(groups)
        cpu_cores_id = encode_path_as_group_id(('cpu-cores',))
        assert 'nestedGroups' not in by_id[cpu_cores_id]

    def test_empty_spans_returns_empty_list(self) -> None:
        assert build_groups_wire([]) == []

    def test_roots_appear_before_leaves_in_output(self) -> None:
        groups = build_groups_wire(self._make_fixture_spans())
        root_ids = {
            encode_path_as_group_id(('app-A',)),
            encode_path_as_group_id(('cpu-cores',)),
        }
        all_ids = [group['id'] for group in groups]
        root_positions = [i for i, gid in enumerate(all_ids) if gid in root_ids]
        non_root_positions = [i for i, gid in enumerate(all_ids) if gid not in root_ids]
        assert max(root_positions) < min(non_root_positions)

    def test_group_count_includes_synthetic_ancestors(self) -> None:
        # paths: ('app-A',), ('app-A','plug-1'), ('app-A','plug-1','alpha'), ('cpu-cores',) = 4
        groups = build_groups_wire(self._make_fixture_spans())
        assert len(groups) == 4

    def test_single_flat_span_produces_one_group_no_nesting(self) -> None:
        spans = [make_clipped(path=['standalone'])]
        groups = build_groups_wire(spans)
        assert len(groups) == 1
        assert groups[0]['content'] == 'standalone'
        assert 'nestedGroups' not in groups[0]

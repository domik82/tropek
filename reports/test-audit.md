# Test Coverage Audit

- Pact interactions: 0 (no pact file — Phase 2 not yet landed)
- OpenAPI endpoints: 100 (all covered by schemathesis unless excluded)
- Integration test functions inspected: 798

| File | Test | Classification | Docstring (first line) |
| --- | --- | --- | --- |
| `api/tests/asset_meta/db/test_ingest_endpoint.py` | `test_post_snapshot_closed_only_returns_201` | api-shape-check (candidate for schemathesis coverage) |  |
| `api/tests/asset_meta/db/test_ingest_endpoint.py` | `test_post_snapshot_duplicate_path_in_values_returns_422` | api-shape-check (candidate for schemathesis coverage) |  |
| `api/tests/asset_meta/db/test_ingest_endpoint.py` | `test_post_snapshot_empty_body_returns_422` | api-shape-check (candidate for schemathesis coverage) |  |
| `api/tests/asset_meta/db/test_ingest_endpoint.py` | `test_post_snapshot_invalid_source_returns_422` | api-shape-check (candidate for schemathesis coverage) |  |
| `api/tests/asset_meta/db/test_ingest_endpoint.py` | `test_post_snapshot_naive_datetime_returns_422` | api-shape-check (candidate for schemathesis coverage) |  |
| `api/tests/asset_meta/db/test_ingest_endpoint.py` | `test_post_snapshot_path_too_deep_returns_422` | api-shape-check (candidate for schemathesis coverage) |  |
| `api/tests/asset_meta/db/test_ingest_endpoint.py` | `test_post_snapshot_persists_values_and_closures_to_db` | api-shape-check (candidate for schemathesis coverage) |  |
| `api/tests/asset_meta/db/test_ingest_endpoint.py` | `test_post_snapshot_unknown_asset_returns_404` | api-shape-check (candidate for schemathesis coverage) |  |
| `api/tests/asset_meta/db/test_ingest_endpoint.py` | `test_post_snapshot_values_only_returns_201` | api-shape-check (candidate for schemathesis coverage) |  |
| `api/tests/asset_meta/db/test_read_endpoint.py` | `test_cascading_closure_round_trip` | api-shape-check (candidate for schemathesis coverage) | POST values at T0, close parent at T1 — all children close at T1. |
| `api/tests/asset_meta/db/test_read_endpoint.py` | `test_closed_only_snapshot_round_trip` | api-shape-check (candidate for schemathesis coverage) | POST values at T0, close at T1 — single closed item in timeline. |
| `api/tests/asset_meta/db/test_read_endpoint.py` | `test_large_snapshot_roundtrips` | api-shape-check (candidate for schemathesis coverage) | POST a snapshot with 500 values — all appear in the timeline. |
| `api/tests/asset_meta/db/test_read_endpoint.py` | `test_multi_source_spans_both_appear` | api-shape-check (candidate for schemathesis coverage) | Two sources push different paths — both appear in the timeline. |
| `api/tests/asset_meta/db/test_read_endpoint.py` | `test_round_trip_single_snapshot_shows_up_in_timeline` | api-shape-check (candidate for schemathesis coverage) | POST one snapshot with one value, GET timeline — assert 1 item. |
| `api/tests/asset_meta/db/test_read_endpoint.py` | `test_unknown_asset_returns_404` | api-shape-check (candidate for schemathesis coverage) | GET for a random UUID returns 404. |
| `api/tests/asset_meta/db/test_read_endpoint.py` | `test_validation_error_when_from_equals_or_exceeds_to` | api-shape-check (candidate for schemathesis coverage) | GET with from=to or from>to returns 422. |
| `api/tests/asset_meta/db/test_read_endpoint.py` | `test_validation_errors_for_missing_from_or_to` | unclassified (human review) | GET without from or to returns 422. |
| `api/tests/asset_meta/db/test_read_endpoint.py` | `test_window_clipping_left_and_open_right` | api-shape-check (candidate for schemathesis coverage) | A span started 60 days ago with no close, queried for last 30 days — clipped left and open right. |
| `api/tests/asset_meta/db/test_repository.py` | `test_asset` | business-logic / db-state (keep) | Create a minimal asset for FK satisfaction. |
| `api/tests/asset_meta/db/test_repository.py` | `test_cascade_delete_when_asset_removed` | business-logic / db-state (keep) | Deleting an asset should cascade-delete all snapshots, values, and closures. |
| `api/tests/asset_meta/db/test_repository.py` | `test_insert_closures_persists_all_entries` | business-logic / db-state (keep) | insert_closures should persist all provided closure paths. |
| `api/tests/asset_meta/db/test_repository.py` | `test_insert_snapshot_returns_row_with_generated_id` | unclassified (human review) | insert_snapshot should return a persisted row with all fields populated. |
| `api/tests/asset_meta/db/test_repository.py` | `test_insert_values_persists_all_entries` | business-logic / db-state (keep) | insert_values should persist all provided key-value entries. |
| `api/tests/asset_meta/db/test_repository.py` | `test_load_snapshots_for_derivation_hydrates_values_and_closures` | unclassified (human review) | Returned SnapshotRows should include associated values and closures. |
| `api/tests/asset_meta/db/test_repository.py` | `test_load_snapshots_for_derivation_orders_by_observed_then_id` | unclassified (human review) | Snapshots with identical observed_at should be ordered by id ASC. |
| `api/tests/asset_meta/db/test_repository.py` | `test_load_snapshots_for_derivation_respects_until_bound` | unclassified (human review) | load_snapshots_for_derivation should only return snapshots with observed_at <= until. |
| `api/tests/asset_meta/db/test_summary_endpoint.py` | `test_summary_404_for_unknown_asset` | api-shape-check (candidate for schemathesis coverage) | GET summary for a random UUID returns 404. |
| `api/tests/asset_meta/db/test_summary_endpoint.py` | `test_summary_and_timeline_count_parity` | api-shape-check (candidate for schemathesis coverage) | summary itemCount == number of distinct group values in full timeline items. |
| `api/tests/asset_meta/db/test_summary_endpoint.py` | `test_summary_count_grows_with_distinct_paths` | api-shape-check (candidate for schemathesis coverage) | POST 3 distinct paths → count 3; POST a 4th → count 4. |
| `api/tests/asset_meta/db/test_summary_endpoint.py` | `test_summary_returns_zero_for_empty_asset` | api-shape-check (candidate for schemathesis coverage) | GET summary for an asset with no snapshots — item count is 0. |
| `api/tests/asset_meta/db/test_summary_endpoint.py` | `test_summary_validation_error_when_from_equals_or_exceeds_to` | api-shape-check (candidate for schemathesis coverage) | GET summary with from == to or from > to returns 422. |
| `api/tests/asset_meta/test_schemas.py` | `test_duplicate_path_in_closed_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_duplicate_path_in_values_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_empty_path_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_empty_path_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_empty_source_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_empty_string_accepted` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_empty_string_entry_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_empty_string_entry_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_empty_values_and_closed_accepted_by_pydantic` | unclassified (human review) | Both lists empty is valid at the schema level. |
| `api/tests/asset_meta/test_schemas.py` | `test_entry_exceeding_128_chars_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_entry_exceeding_128_chars_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_naive_datetime_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_same_path_in_values_and_closed_accepted` | unclassified (human review) | Close-and-reopen: same path appearing in both values and closed is valid. |
| `api/tests/asset_meta/test_schemas.py` | `test_seven_entry_path_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_seven_entry_path_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_source_exceeding_64_chars_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_source_with_dots_dashes_underscores_accepted` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_source_with_exclamation_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_source_with_space_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_timezone_aware_datetime_accepted` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_unknown_field_rejected` | unclassified (human review) | StrictInput sets extra='forbid' — unknown fields must be rejected. |
| `api/tests/asset_meta/test_schemas.py` | `test_valid_path_accepted` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_valid_six_entry_path_accepted` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_valid_source_accepted` | unclassified (human review) |  |
| `api/tests/asset_meta/test_schemas.py` | `test_value_exceeding_1024_chars_rejected` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_ensure_asset_exists_raises_not_found` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_ensure_asset_exists_silent_when_present` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_get_timeline_raises_not_found_for_missing_asset` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_get_timeline_returns_empty_for_no_snapshots` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_get_timeline_summary_raises_not_found_for_missing_asset` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_get_timeline_summary_returns_zero_for_empty_asset` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_validate_payload_has_content_accepts_both` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_validate_payload_has_content_accepts_closed_only` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_validate_payload_has_content_accepts_values_only` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_validate_payload_has_content_rejects_empty` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_write_snapshot_rows_both` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_write_snapshot_rows_closed_only` | unclassified (human review) |  |
| `api/tests/asset_meta/test_service.py` | `test_write_snapshot_rows_values_only` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_all_spans_inside_window_all_returned` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_all_spans_outside_window_returns_empty` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_closed_span_carries_closed_class` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_compute_span_classes` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_empty_input_returns_empty_list` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_mix_keeps_only_in_window_spans` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_mix_result_count_matches_in_window_count` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_open_span_is_clipped_to_window_to_with_open_class` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_overlapping_span_is_included_and_clipped` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_returned_clipped_span_is_a_clipped_span_instance` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_source_path_value_are_preserved` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_span_end_exactly_at_window_from_returns_none` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_span_entirely_after_window_returns_none` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_span_entirely_before_window_returns_none` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_span_fully_inside_window_is_unchanged` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_span_overlapping_left_is_clipped_and_has_clipped_left_class` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_span_overlapping_right_is_clipped_and_has_clipped_right_class` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_span_start_exactly_at_window_to_returns_none` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_clipping.py` | `test_zero_length_span_inside_window` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_emits_warning_with_correct_extra_fields` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_empty_input_returns_empty_dict` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_multi_path_input_with_duplicates_within_path` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_multiple_spans_same_source_takes_latest` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_open_span_beats_closed_past_span` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_single_path_input_produces_one_key` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_single_source_path_passes_through_unchanged` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_single_source_returns_itself` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_three_sources_same_path_picks_correct_winner` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_tie_on_timestamp_alphabetical_source_wins` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_two_source_conflict_drops_loser_emits_warning` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_two_sources_winner_based_on_latest_end` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_conflict_resolution.py` | `test_unambiguous_winner` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_cascading_close` | unclassified (human review) | Open app + app/plug + app/plug/alpha, then close app -> three closed spans (scenario 19). |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_closes_descendants_of_same_source` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_closes_exact_match` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_closures_before_values_ordering` | unclassified (human review) | Open 'foo' at T0, snapshot at T1 closes 'foo' then re-opens with new value. |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_closures_only_snapshot` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_converts_remaining_to_open_ended_spans` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_daily_heartbeat_collapses` | unclassified (human review) | 30 identical snapshots should collapse into exactly one open-ended span (scenario 9). |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_different_value_closes_old_and_opens_new` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_disjoint` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_does_not_touch_other_sources` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_empty_map_produces_nothing` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_empty_prefix_on_empty` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_empty_prefix_on_non_empty` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_equal_tuples` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_new_key_opens_span` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_noop_when_no_open_span` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_same_value_is_noop` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_single_value_snapshot` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_strict_prefix` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_suffix_not_prefix` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_value_then_value_change` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_derivation.py` | `test_values_only_snapshot` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_class_name_matches_span` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_content_equals_value` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_empty_spans_returns_empty_list` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_end_is_iso_string` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_group_encodes_path` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_id_uses_index` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_ids_are_sequential` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_length_matches_span_count` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_source_matches_span` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_start_is_iso_string` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_item_emitter.py` | `test_type_is_range` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_clipped_left_class` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_closed_class` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_collapses_to_one_item` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_collapses_to_one_item` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_empty_result` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_exactly_one_item` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_first_closed_second_open` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_first_has_end_reason_style` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_one_group_one_item` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_one_item_closed` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_only_winner_items` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_open_span_class` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_open_span_gets_open_class` | unclassified (human review) | Open span (end=None) → 'meta-span-open'. |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_other_source_span_still_open` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_source_a_one_continuous_span` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_span_closed_within_window_gets_closed_class` | unclassified (human review) | Span ends within window with closure → 'meta-span-closed'. |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_span_ending_after_window_gets_clipped_right` | unclassified (human review) | Span ends after window_to → 'meta-span-clipped-right'. |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_three_groups_from_leaf_only` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_three_items_all_closed` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_three_items_all_closed_at_t1` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_two_items` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_two_items_for_path` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_warning_logged` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_orchestrator.py` | `test_zero_items` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_summary.py` | `test_count_distinct_leaf_paths_deduplicates` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_summary.py` | `test_count_distinct_leaf_paths_empty` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_already_expanded_input_is_idempotent` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_app_a_has_plug_1_in_nested_groups` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_content_is_last_path_segment` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_cpu_cores_has_no_nested_groups` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_different_paths_all_preserved` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_duplicate_paths_deduplicated` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_empty_input_returns_empty_list` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_empty_input_returns_empty_set` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_empty_paths_returns_empty_map` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_empty_spans_returns_empty_list` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_empty_spans_returns_empty_set` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_group_count_includes_synthetic_ancestors` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_leaf_entry_has_only_id_and_content` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_leaf_node_absent_as_key` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_leaf_only_produces_all_ancestor_prefixes` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_lexicographic_within_same_depth` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_mixed_depths` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_multi_segment` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_nested_groups_are_sorted_deterministically` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_nested_groups_contains_encoded_child_ids` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_parent_entry_has_nested_groups_and_show_nested` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_parent_with_two_children_both_listed` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_path_with_colon_preserved` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_path_with_single_quote_is_json_safe` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_path_with_slash_preserved` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_plug_1_has_alpha_in_nested_groups` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_root_path_parent_not_emitted` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_roots_appear_before_leaves_in_output` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_roots_before_depth_two` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_round_trip_restores_original_list` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_same_input_different_orderings_produce_identical_output` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_simple_single_segment` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_single_flat_span_produces_one_group_no_nesting` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_single_root_stays_as_root` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_synthetic_intermediate_ancestor_emitted` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_three_level_hierarchy` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_two_sibling_leaves_share_ancestor` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_tree_builder.py` | `test_unicode_preserved_not_escaped` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_types.py` | `test_clipped_span_fields` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_types.py` | `test_open_span_fields` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_types.py` | `test_open_span_map_is_dict_type` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_types.py` | `test_raw_span_fields` | unclassified (human review) |  |
| `api/tests/asset_meta/timeline/test_types.py` | `test_snapshot_with_entries_fields` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_create_and_get` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_delete` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_delete_not_found` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_delete_removes_group_memberships` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_group_add_remove_member` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_group_create_with_members` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_group_tree_top_level` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_list_filter_by_type` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_type_create_and_get` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_type_delete_in_use_raises` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_type_delete_unused` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_type_list_includes_count` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_type_rename` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_type_rename_duplicate` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_type_rename_not_found` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_type_set_default_swaps` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_asset_update` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_group_update_properties` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_tag_keys_aggregation` | unclassified (human review) |  |
| `api/tests/assets/db/test_asset_repositories.py` | `test_tag_values_for_key` | unclassified (human review) |  |
| `api/tests/assignments/db/test_assignments.py` | `test_create_group_assignment` | unclassified (human review) |  |
| `api/tests/assignments/db/test_assignments.py` | `test_create_slo_assignment_for_asset` | unclassified (human review) |  |
| `api/tests/assignments/db/test_assignments.py` | `test_create_slo_assignment_for_group` | unclassified (human review) |  |
| `api/tests/assignments/db/test_assignments.py` | `test_resolve_direct_asset_assignment` | unclassified (human review) |  |
| `api/tests/assignments/db/test_assignments.py` | `test_resolve_direct_asset_wins_over_group` | unclassified (human review) |  |
| `api/tests/assignments/db/test_assignments.py` | `test_slo_assignment_unique_per_slo_name` | unclassified (human review) |  |
| `api/tests/assignments/db/test_assignments.py` | `test_upgrade_slo_assignment` | unclassified (human review) |  |
| `api/tests/assignments/db/test_binding_resolution.py` | `test_direct_assignment_overrides_group` | unclassified (human review) | Same SLO name assigned both directly and via group — direct wins. |
| `api/tests/assignments/db/test_binding_resolution.py` | `test_direct_assignment_overrides_template` | unclassified (human review) | Direct SLO assignment overrides template-generated SLO with same name. |
| `api/tests/assignments/db/test_binding_resolution.py` | `test_evaluate_direct_slo_assignment` | unclassified (human review) | Asset with direct SLO assignment — evaluation discovers the SLO. |
| `api/tests/assignments/db/test_binding_resolution.py` | `test_evaluate_direct_template_assignment` | unclassified (human review) | SLO group assigned directly to asset — template-generated SLOs discovered. |
| `api/tests/assignments/db/test_binding_resolution.py` | `test_evaluate_group_slo_assignment` | unclassified (human review) | Asset in group — SLO assigned to group is discovered for the asset. |
| `api/tests/assignments/db/test_binding_resolution.py` | `test_evaluate_group_template_assignment` | unclassified (human review) | SLO group assigned to asset group — template-generated SLOs discovered. |
| `api/tests/assignments/db/test_binding_resolution.py` | `test_mixed_binding_types_all_discovered` | unclassified (human review) | Asset with direct SLO + group SLO + template SLOs — all discovered. |
| `api/tests/cache/test_redis_cache.py` | `test_cache_hit_skips_loader` | unclassified (human review) |  |
| `api/tests/cache/test_redis_cache.py` | `test_cache_miss_calls_loader` | unclassified (human review) |  |
| `api/tests/cache/test_redis_cache.py` | `test_cache_miss_loader_returns_none` | unclassified (human review) | If loader returns None, don't cache it. |
| `api/tests/cache/test_redis_cache.py` | `test_cache_with_ttl` | unclassified (human review) |  |
| `api/tests/cache/test_redis_cache.py` | `test_invalidate_key` | unclassified (human review) |  |
| `api/tests/common/db/test_tag_mixin.py` | `test_get_tag_keys_returns_empty_when_no_tags` | unclassified (human review) |  |
| `api/tests/common/db/test_tag_mixin.py` | `test_get_tag_values_returns_empty_for_missing_key` | unclassified (human review) |  |
| `api/tests/common/test_exceptions.py` | `test_conflict_error_message` | unclassified (human review) |  |
| `api/tests/common/test_exceptions.py` | `test_conflict_is_domain_error` | unclassified (human review) |  |
| `api/tests/common/test_exceptions.py` | `test_domain_validation_error_message` | unclassified (human review) |  |
| `api/tests/common/test_exceptions.py` | `test_domain_validation_is_domain_error` | unclassified (human review) |  |
| `api/tests/common/test_exceptions.py` | `test_not_found_error_message` | unclassified (human review) |  |
| `api/tests/common/test_exceptions.py` | `test_not_found_is_domain_error` | unclassified (human review) |  |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_create_and_get` | unclassified (human review) |  |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_delete_by_name_not_found` | unclassified (human review) | delete_by_name returns False for nonexistent datasource. |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_delete_by_name_success` | unclassified (human review) | delete_by_name removes a datasource with no active SLO links. |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_delete_removes_record` | unclassified (human review) |  |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_get_by_name_missing_returns_none` | unclassified (human review) |  |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_get_tag_keys` | unclassified (human review) | get_tag_keys returns distinct keys with counts. |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_get_tag_values` | unclassified (human review) | get_tag_values returns distinct values for a key with counts. |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_list_all` | unclassified (human review) |  |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_list_all_filter_by_adapter_type` | unclassified (human review) |  |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_list_all_filters_by_tag` | unclassified (human review) | list_all with tag_key/tag_val filters returns matching datasources. |
| `api/tests/datasource/db/test_datasource_repository.py` | `test_update_adapter_url` | unclassified (human review) |  |
| `api/tests/db/test_annotation_category_repository.py` | `test_create_adds_row` | unclassified (human review) |  |
| `api/tests/db/test_annotation_category_repository.py` | `test_delete_reassigns_referencing_annotations` | unclassified (human review) | Deleting a category with references must move them to 'info' and return the count. |
| `api/tests/db/test_annotation_category_repository.py` | `test_delete_rejects_system_rows` | unclassified (human review) |  |
| `api/tests/db/test_annotation_category_repository.py` | `test_delete_returns_zero_when_unused` | unclassified (human review) |  |
| `api/tests/db/test_annotation_category_repository.py` | `test_get_by_name_returns_category` | unclassified (human review) |  |
| `api/tests/db/test_annotation_category_repository.py` | `test_list_all_returns_seeded_rows` | unclassified (human review) |  |
| `api/tests/db/test_annotation_category_repository.py` | `test_update_modifies_fields` | unclassified (human review) |  |
| `api/tests/db/test_annotation_category_repository.py` | `test_update_rejects_name_change_on_system` | unclassified (human review) |  |
| `api/tests/db/test_note_category_router.py` | `test_create_category` | unclassified (human review) |  |
| `api/tests/db/test_note_category_router.py` | `test_create_rejects_bad_color` | unclassified (human review) |  |
| `api/tests/db/test_note_category_router.py` | `test_create_rejects_long_label` | unclassified (human review) |  |
| `api/tests/db/test_note_category_router.py` | `test_delete_non_system_returns_reassigned_count` | unclassified (human review) |  |
| `api/tests/db/test_note_category_router.py` | `test_delete_system_rejected` | unclassified (human review) |  |
| `api/tests/db/test_note_category_router.py` | `test_list_returns_seeded` | unclassified (human review) |  |
| `api/tests/db/test_note_category_router.py` | `test_update_system_label_ok` | unclassified (human review) |  |
| `api/tests/db/test_note_category_router.py` | `test_update_system_name_rejected` | unclassified (human review) |  |
| `api/tests/display_groups/db/test_display_groups.py` | `test_add_member` | unclassified (human review) |  |
| `api/tests/display_groups/db/test_display_groups.py` | `test_create_display_group` | unclassified (human review) |  |
| `api/tests/display_groups/db/test_display_groups.py` | `test_create_nested_display_group` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_baseline_query.py` | `test_baselines_exclude_invalidated` | unclassified (human review) | Invalidated evaluations must not appear in baseline results. |
| `api/tests/quality_gate/db/test_baseline_query.py` | `test_baselines_return_pass_only` | unclassified (human review) | When include_result_with_score='pass', only passing evals returned. |
| `api/tests/quality_gate/db/test_column_annotations.py` | `test_column_annotations_404_for_unknown_run` | unclassified (human review) | Returns 404 when the evaluation_id does not exist. |
| `api/tests/quality_gate/db/test_column_annotations.py` | `test_column_annotations_empty_when_no_annotations` | business-logic / db-state (keep) | Returns empty list when the run has no annotations. |
| `api/tests/quality_gate/db/test_column_annotations.py` | `test_column_annotations_excludes_hidden` | api-shape-check (candidate for schemathesis coverage) | Hidden annotations are excluded from the response. |
| `api/tests/quality_gate/db/test_column_annotations.py` | `test_column_annotations_returns_all_slo_annotations` | unclassified (human review) | GET /evaluations/column-annotations returns annotations from all SLOs in the run. |
| `api/tests/quality_gate/db/test_column_annotations.py` | `test_column_annotations_unions_run_level_and_slo_level` | business-logic / db-state (keep) | Run-level notes (new UI form) and SLO-level notes (re-eval) are both returned. |
| `api/tests/quality_gate/db/test_duplicate_prevention.py` | `test_create_pending_raises_on_constraint_violation` | unclassified (human review) | Simulate a race condition where two creates pass the app-level check. |
| `api/tests/quality_gate/db/test_duplicate_prevention.py` | `test_find_duplicate_different_name_no_conflict` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_duplicate_prevention.py` | `test_find_duplicate_ignores_failed` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_duplicate_prevention.py` | `test_find_duplicate_returns_existing_completed` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_duplicate_prevention.py` | `test_find_duplicate_returns_none_when_no_match` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_duplicate_prevention.py` | `test_find_duplicate_returns_pending` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_evaluation_names.py` | `test_evaluation_names_empty_when_no_evals` | unclassified (human review) | Returns empty list when no evaluations match. |
| `api/tests/quality_gate/db/test_evaluation_names.py` | `test_evaluation_names_returns_distinct_names` | unclassified (human review) | Endpoint returns distinct names with count and last_run, sorted by last_run DESC. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_add_and_list_annotations` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_create_pending_merges_asset_tags_into_variables` | business-logic / db-state (keep) | Asset tags become defaults in variables; caller values take precedence. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_create_pending_returns_evaluation` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_get_baselines_by_asset_and_slo` | unclassified (human review) | Baselines scoped by asset_id + slo_name, not by evaluation_name. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_get_baselines_excludes_future_period_start` | unclassified (human review) | Baselines must have period_start strictly before the current evaluation. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_get_baselines_excludes_invalidated` | unclassified (human review) | Invalidated evaluations are excluded from baselines. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_get_baselines_excludes_null_sli_version_with_range` | unclassified (human review) | Evaluations with null sli_version are excluded when a range is specified. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_get_baselines_restrict_to_ids` | unclassified (human review) | restrict_to_ids limits baselines to a specific set of evaluation IDs. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_get_baselines_with_sli_version_range` | unclassified (human review) | Version range filter excludes evaluations outside the compatible range. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_get_baselines_with_tag_filters` | unclassified (human review) | Tag filters narrow baselines by variables JSONB values. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_get_returns_evaluation` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_hide_annotation` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_list_evaluations_filters_by_name` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_list_with_counts_eager_loads_latest_annotation_category` | unclassified (human review) | ``latest_map`` entries must have their ``category`` relationship pre-loaded. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_mark_completed_updates_fields` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_mark_running_sets_status` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_override_double_apply_preserves_original` | unclassified (human review) | Second override must NOT overwrite original_result from the first eval. |
| `api/tests/quality_gate/db/test_evaluation_repository.py` | `test_write_and_read_sli_values` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_evaluation_run_repository.py` | `test_create_and_get` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_evaluation_run_repository.py` | `test_finalize_skips_when_not_all_done` | business-logic / db-state (keep) |  |
| `api/tests/quality_gate/db/test_evaluation_run_repository.py` | `test_finalize_worst_case_result` | business-logic / db-state (keep) |  |
| `api/tests/quality_gate/db/test_evaluation_run_repository.py` | `test_find_finalizable_pending_ids_respects_limit_and_order` | business-logic / db-state (keep) | limit caps the result count, oldest period_end comes first. |
| `api/tests/quality_gate/db/test_evaluation_run_repository.py` | `test_find_finalizable_pending_ids_returns_all_terminal` | business-logic / db-state (keep) | Parent whose children are all completed/failed is returned. |
| `api/tests/quality_gate/db/test_evaluation_run_repository.py` | `test_find_finalizable_pending_ids_skips_completed_parent` | business-logic / db-state (keep) | Parent already in 'completed' status is skipped. |
| `api/tests/quality_gate/db/test_evaluation_run_repository.py` | `test_find_finalizable_pending_ids_skips_pending_child` | business-logic / db-state (keep) | Parent with at least one pending/running/partial child is skipped. |
| `api/tests/quality_gate/db/test_evaluation_run_repository.py` | `test_find_finalizable_pending_ids_skips_zero_children` | unclassified (human review) | Parent with no children at all is skipped. |
| `api/tests/quality_gate/db/test_finalize_sweeper.py` | `test_sweeper_and_finalize_run_job_converge` | unclassified (human review) | Both the fast-path finalize_run_job and the sweeper target the same parent. |
| `api/tests/quality_gate/db/test_finalize_sweeper.py` | `test_sweeper_idempotent_on_already_finalized` | unclassified (human review) | Calling sweeper twice on the same stuck run leaves state consistent. |
| `api/tests/quality_gate/db/test_finalize_sweeper.py` | `test_sweeper_rescues_single_stuck_run` | unclassified (human review) | One stuck run gets finalized by the sweeper. |
| `api/tests/quality_gate/db/test_finalize_sweeper.py` | `test_sweeper_rescues_when_fast_path_never_ran` | unclassified (human review) | Simulate a worker that committed a child but never enqueued finalize. |
| `api/tests/quality_gate/db/test_finalize_sweeper.py` | `test_sweeper_respects_batch_limit` | unclassified (human review) | More stuck runs than batch_limit: sweeper rescues only batch_limit of them. |
| `api/tests/quality_gate/db/test_finalize_sweeper.py` | `test_sweeper_tick_no_stuck_runs_is_noop` | unclassified (human review) | Empty DB: sweeper tick runs cleanly, no exceptions. |
| `api/tests/quality_gate/db/test_grouped_heatmap.py` | `test_cache_parameter_accepted_and_response_identical_pre_cache` | api-shape-check (candidate for schemathesis coverage) | PR1 contract: ?cache=true and ?cache=false both return identical JSON. |
| `api/tests/quality_gate/db/test_grouped_heatmap.py` | `test_grouped_heatmap_eval_name_filter` | unclassified (human review) | eval_name filter restricts which EvaluationRuns are returned. |
| `api/tests/quality_gate/db/test_grouped_heatmap.py` | `test_grouped_heatmap_excludes_pending_runs` | unclassified (human review) | Pending EvaluationRun rows do not appear in the heatmap. |
| `api/tests/quality_gate/db/test_grouped_heatmap.py` | `test_grouped_heatmap_returns_completed_runs` | unclassified (human review) | Each completed EvaluationRun becomes one column in the grouped response. |
| `api/tests/quality_gate/db/test_grouped_heatmap_has_notes.py` | `test_grouped_heatmap_has_notes_false_when_annotation_hidden` | business-logic / db-state (keep) | A run whose only annotation is soft-deleted reports has_notes=False. |
| `api/tests/quality_gate/db/test_grouped_heatmap_has_notes.py` | `test_grouped_heatmap_has_notes_true_for_annotated_column` | business-logic / db-state (keep) | has_notes is True for a run with an annotation, False for one without. |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_baseline_pin_mutation_deletes_cached_fragment` | business-logic / db-state (keep) | Pin and unpin baseline mutations must also delete the cached fragment. |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_cache_equals_uncached_after_mutation` | api-shape-check (candidate for schemathesis coverage) | Correctness centerpiece of Chunk C: for any sequence of |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_cache_false_does_not_read_or_write_cache` | api-shape-check (candidate for schemathesis coverage) | ``cache=false`` is pure bypass: no Redis read, no Redis write. |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_cache_key_shape` | unclassified (human review) | The cache key embeds the schema version (v1) so a future schema bump |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_corrupted_payload_returns_miss_not_exception` | unclassified (human review) | A malformed JSON payload must be treated as a cache miss, not crash |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_delete_many_removes_all_targets` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_delete_one_removes_only_target` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_get_many_returns_only_hits` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_read_path_cold_cache_writes_back_every_column` | api-shape-check (candidate for schemathesis coverage) | Cold cache: the read path must rebuild every column from the DB and |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_read_path_warm_cache_serves_same_response` | api-shape-check (candidate for schemathesis coverage) | Warm cache: a second read hits the cached fragments and the response |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_reevaluation_persist_deletes_cached_fragment` | business-logic / db-state (keep) | ``_persist_reeval_result`` must delete the cached fragment for the |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_repository_mutation_deletes_cached_fragment` | business-logic / db-state (keep) | Every repository mutation that changes a run's presented state must |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_set_and_get_roundtrips_fragment` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_worker_warm_helper_caches_fragment` | business-logic / db-state (keep) | ``warm_heatmap_column_cache`` builds and caches a fragment for a completed run. |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_worker_warm_helper_is_fire_and_forget_on_missing_run` | unclassified (human review) | A missing run must not raise — the helper logs and returns. |
| `api/tests/quality_gate/db/test_heatmap_cache.py` | `test_worker_warm_helper_noop_when_redis_cache_is_none` | business-logic / db-state (keep) | If no RedisCache is configured, the helper short-circuits without touching the DB. |
| `api/tests/quality_gate/db/test_heatmap_query.py` | `test_heatmap_includes_invalidated_completed` | unclassified (human review) | The repository query returns invalidated evals (router handles display). |
| `api/tests/quality_gate/db/test_heatmap_query.py` | `test_heatmap_returns_completed_evals` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_indicator_repository.py` | `test_bulk_insert_and_read_back` | business-logic / db-state (keep) | Write indicator rows, read them back, verify fields match. |
| `api/tests/quality_gate/db/test_indicator_repository.py` | `test_bulk_insert_persists_targets_jsonb` | business-logic / db-state (keep) | Targets JSONB is stored and readable. |
| `api/tests/quality_gate/db/test_indicator_repository.py` | `test_delete_and_reinsert` | business-logic / db-state (keep) | Re-evaluation pattern: delete old rows, insert new set. |
| `api/tests/quality_gate/db/test_indicator_round_trip.py` | `test_detail_round_trip_all_fields` | unclassified (human review) | Write indicator rows with all field types, read back via presenter, assert equality. |
| `api/tests/quality_gate/db/test_indicator_round_trip.py` | `test_empty_indicator_results` | unclassified (human review) | Evaluation with no indicators produces empty lists. |
| `api/tests/quality_gate/db/test_indicator_round_trip.py` | `test_summary_top_failures` | unclassified (human review) | Summary extracts only failing indicators into top_failures. |
| `api/tests/quality_gate/db/test_re_evaluation.py` | `test_empty_slo_names_rejected` | unclassified (human review) | An empty slo_names list is rejected — it is ambiguous with omission. |
| `api/tests/quality_gate/db/test_re_evaluation.py` | `test_load_evaluations_for_reeval_excludes_invalidated` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_re_evaluation.py` | `test_load_evaluations_for_reeval_from_date` | unclassified (human review) | load_evaluations_for_reeval returns evals in chronological order from a start date. |
| `api/tests/quality_gate/db/test_re_evaluation.py` | `test_persist_reeval_result_preserves_original` | unclassified (human review) | First re-eval sets original_result in job_stats; second re-eval does not overwrite. |
| `api/tests/quality_gate/db/test_re_evaluation.py` | `test_re_evaluate_cascading_baselines` | unclassified (human review) | Each re-evaluated eval becomes available as a baseline for the next. |
| `api/tests/quality_gate/db/test_re_evaluation.py` | `test_re_evaluate_dry_run_does_not_write` | unclassified (human review) | Dry run returns diffs without modifying the database. |
| `api/tests/quality_gate/db/test_re_evaluation.py` | `test_re_evaluate_filters_to_slo_names_subset` | unclassified (human review) | slo_names filters re-evaluation to only the listed SLOs on the asset. |
| `api/tests/quality_gate/db/test_re_evaluation.py` | `test_re_evaluate_updates_results_and_adds_annotation` | unclassified (human review) | Full re-evaluation flow: create evals, re-eval with new SLO, verify results. |
| `api/tests/quality_gate/db/test_re_evaluation.py` | `test_slo_name_and_slo_names_mutually_exclusive` | unclassified (human review) | Supplying both slo_name and slo_names is rejected at schema level. |
| `api/tests/quality_gate/db/test_re_evaluation.py` | `test_slo_names_happy_path` | unclassified (human review) | slo_names round-trips and leaves slo_name unset. |
| `api/tests/quality_gate/db/test_trend_query.py` | `test_trend_excludes_invalidated` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_trend_query.py` | `test_trend_returns_points_with_baseline` | unclassified (human review) |  |
| `api/tests/quality_gate/db/test_trend_query.py` | `test_trend_returns_targets_from_indicator_row` | unclassified (human review) | Trend points include the stored targets JSONB from indicator_results. |
| `api/tests/quality_gate/db/test_trigger_evaluate.py` | `test_evaluate_batch_by_date` | unclassified (human review) | POST /evaluate/batch with mode=by_date creates one run per period. |
| `api/tests/quality_gate/db/test_trigger_evaluate.py` | `test_evaluate_single_creates_run_and_children` | unclassified (human review) | POST /evaluate creates one EvaluationRun + one SLOEvaluation per bound SLO. |
| `api/tests/quality_gate/db/test_trigger_evaluate.py` | `test_evaluate_unknown_asset_returns_404` | unclassified (human review) | POST /evaluate with unknown asset_name returns 404. |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_annotation_appears_in_eval_detail` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_create_annotation` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_create_annotation_on_missing_eval` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_create_run_annotation` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_create_run_annotation_on_missing_run` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_hide_annotation_excludes_from_detail` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_list_annotations` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_list_evaluations_serializes_latest_annotation_category` | unclassified (human review) | Regression guard: GET /evaluations must serialize latest_annotation.category |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_run_annotation_visible_in_column_endpoint` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_trend_annotations_keyed_by_slo_evaluation_id` | unclassified (human review) | Regression guard: trend points are keyed by slo_evaluation_id on the UI |
| `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` | `test_update_annotation` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_baseline_pin_endpoints.py` | `test_pin_baseline` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_baseline_pin_endpoints.py` | `test_pin_new_unpins_previous` | unclassified (human review) | Pinning eval B for the same asset+SLO must atomically unpin eval A. |
| `api/tests/quality_gate/endpoints/test_baseline_pin_endpoints.py` | `test_unpin_baseline` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_heatmap_endpoints.py` | `test_heatmap_invalidated_eval_shows_invalidated_result` | unclassified (human review) | Router transforms invalidated completed eval cells to result='invalidated'. |
| `api/tests/quality_gate/endpoints/test_heatmap_endpoints.py` | `test_heatmap_overridden_eval_shows_overridden_result` | unclassified (human review) | Overridden evaluation cells show the overridden result in heatmap. |
| `api/tests/quality_gate/endpoints/test_invalidation_endpoints.py` | `test_invalidate_evaluation` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_invalidation_endpoints.py` | `test_invalidate_restore_cycle` | unclassified (human review) | Full cycle: valid -> invalidated -> restored to valid. |
| `api/tests/quality_gate/endpoints/test_invalidation_endpoints.py` | `test_restore_invalidated_evaluation` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_override_endpoints.py` | `test_double_override_preserves_true_original` | unclassified (human review) | Overriding an already-overridden eval must keep the FIRST original. |
| `api/tests/quality_gate/endpoints/test_override_endpoints.py` | `test_override_status` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_override_endpoints.py` | `test_restore_override` | unclassified (human review) |  |
| `api/tests/quality_gate/endpoints/test_re_evaluation_endpoints.py` | `test_re_evaluate_preserves_original_on_second_reeval` | unclassified (human review) | Second re-evaluation must NOT overwrite original_result. |
| `api/tests/quality_gate/endpoints/test_re_evaluation_endpoints.py` | `test_re_evaluate_sets_original_result` | unclassified (human review) | First re-evaluation must set original_result and original_score. |
| `api/tests/quality_gate/endpoints/test_smoke.py` | `test_health_endpoint` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_comparison_rules.py` | `test_catch_all_not_last_rejected` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_comparison_rules.py` | `test_empty_rules_valid` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_comparison_rules.py` | `test_invalid_compare_to_type_rejected` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_comparison_rules.py` | `test_invalid_match_type_rejected` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_comparison_rules.py` | `test_multiple_catch_alls_rejected` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_comparison_rules.py` | `test_valid_catch_all_last` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_comparison_rules.py` | `test_valid_negation_rule` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_comparison_rules.py` | `test_valid_pinned_compare_to` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_comparison_rules.py` | `test_valid_single_rule` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_aggregate_avg` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_aggregate_empty_raises` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_aggregate_p50` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_aggregate_p90` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_aggregate_p95` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_aggregate_single_value` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_aggregate_unknown_function_raises` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_fixed_eq_fail` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_fixed_eq_pass` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_fixed_gt_pass` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_fixed_lt_fail` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_fixed_lt_pass` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_fixed_lte_pass_equal` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_invalid_criteria_raises` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_decimal_percentage` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_fixed_eq` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_fixed_gte` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_fixed_lt` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_fixed_lte` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_negative_sign_without_pct_is_relative` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_relative_minus_pct` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_relative_no_sign_defaults_plus` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_relative_plus_pct` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_sign_without_pct_is_relative` | unclassified (human review) | <=+10 (no %) with explicit sign → relative, matching Go behaviour. |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_parse_whitespace_in_criteria` | unclassified (human review) | Keptn lighthouse allowed whitespace around operator and % sign. |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_relative_minus_pct` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_relative_no_baseline_always_passes` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_relative_plus_exceeds_threshold` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_relative_plus_within_threshold` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_target_value_fixed` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_target_value_relative_minus` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_target_value_relative_no_baseline` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria.py` | `test_target_value_relative_plus` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_aggregate_avg_with_negative_values` | unclassified (human review) | Average handles negative values correctly. |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_aggregate_empty_values_raises` | unclassified (human review) | Aggregating empty list raises ValueError. |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_aggregate_p50_with_three_values` | unclassified (human review) | p50 of [1, 2, 3]: idx = int(3 * 50 / 100) = 1 → sorted[1] = 2. |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_aggregate_p99_with_two_values` | unclassified (human review) | p99 of [10, 20]: idx = int(2 * 99 / 100) = 1 → sorted[1] = 20. |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_aggregate_single_value_p90` | unclassified (human review) | Single value returns that value for any percentile function. |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_aggregate_single_value_p99` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_relative_minus_pct_negative_baseline_pass` | unclassified (human review) | >=-10% with baseline=-100: target = -90. Value -85 >= -90 → pass. |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_relative_minus_pct_with_negative_baseline` | unclassified (human review) | >=-10% with baseline=-100: target = -100 - (-100*10/100) = -90. Value -95 < -90 → fail. |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_relative_percent_with_negative_baseline` | unclassified (human review) | <=+10% with baseline=-100: target = -100 + (-100*10/100) = -110. Value -90 > -110 → fail. |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_relative_percent_with_zero_baseline` | unclassified (human review) | <=+10% with baseline=0: target = 0 + 0*10% = 0. Value 0.5 > 0 → fail, not ZeroDivisionError. |
| `api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py` | `test_relative_percent_zero_baseline_zero_value` | unclassified (human review) | <=+10% with baseline=0, value=0: target=0, 0 <= 0 → pass. |
| `api/tests/quality_gate/evaluation_engine/test_evaluator.py` | `test_all_pass_no_baseline` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_evaluator.py` | `test_change_relative_pct_computed` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_evaluator.py` | `test_compared_evaluation_ids_stored` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_evaluator.py` | `test_indicator_results_contain_all_metrics` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_evaluator.py` | `test_indicator_results_count` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_evaluator.py` | `test_key_sli_fail_overrides_score` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_evaluator.py` | `test_missing_metric_fails_objective` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_evaluator.py` | `test_pass_targets_included` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_evaluator.py` | `test_relative_criteria_exceeded_falls_to_warning` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_evaluator.py` | `test_relative_criteria_with_baseline_pass` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_evaluator_failures.py` | `test_all_metrics_return_none` | unclassified (human review) | When all SLI queries return None (adapter error), result should be fail. |
| `api/tests/quality_gate/evaluation_engine/test_evaluator_failures.py` | `test_all_passing_with_baselines` | unclassified (human review) | All metrics pass with relative criteria and baselines. |
| `api/tests/quality_gate/evaluation_engine/test_evaluator_failures.py` | `test_key_sli_fails_means_overall_fail` | unclassified (human review) | If a key_sli objective fails, overall result is fail regardless of score. |
| `api/tests/quality_gate/evaluation_engine/test_evaluator_failures.py` | `test_key_sli_none_value_fails_overall` | unclassified (human review) | key_sli with None metric value should fail the overall evaluation. |
| `api/tests/quality_gate/evaluation_engine/test_evaluator_failures.py` | `test_missing_metric_key_not_in_dict` | unclassified (human review) | Metric not present in dict at all (not even as None) should be treated as None. |
| `api/tests/quality_gate/evaluation_engine/test_evaluator_failures.py` | `test_some_metrics_return_none` | unclassified (human review) | When some metrics succeed and some fail, score is based on available ones. |
| `api/tests/quality_gate/evaluation_engine/test_generator.py` | `test_generate_empty_list` | unclassified (human review) | Empty gen_variables list raises ValueError. |
| `api/tests/quality_gate/evaluation_engine/test_generator.py` | `test_generate_happy_path` | unclassified (human review) | 3 gen_variables rows produce 3 specs with correct substitution. |
| `api/tests/quality_gate/evaluation_engine/test_generator.py` | `test_generate_mismatched_lengths` | unclassified (human review) | Mismatched gen_variables list lengths raise ValueError. |
| `api/tests/quality_gate/evaluation_engine/test_generator.py` | `test_generate_multi_variable` | unclassified (human review) | Multiple gen_variables produce row-aligned substitution. |
| `api/tests/quality_gate/evaluation_engine/test_generator.py` | `test_generate_no_keys` | unclassified (human review) | Empty gen_variables dict raises ValueError. |
| `api/tests/quality_gate/evaluation_engine/test_generator.py` | `test_generate_objectives_not_substituted` | unclassified (human review) | Objectives are copied as-is — $__gen_ in objectives is NOT substituted. |
| `api/tests/quality_gate/evaluation_engine/test_generator.py` | `test_generate_special_chars_in_values` | unclassified (human review) | Special characters in gen_variable values are preserved. |
| `api/tests/quality_gate/evaluation_engine/test_generator.py` | `test_generate_warns_no_gen_placeholders` | unclassified (human review) | Template without $__gen_ placeholders produces a warning. |
| `api/tests/quality_gate/evaluation_engine/test_generator.py` | `test_validate_gen_variables_valid` | unclassified (human review) | Valid gen_variables return no errors. |
| `api/tests/quality_gate/evaluation_engine/test_regeneration.py` | `test_criteria_only_change_preserves_baseline` | unclassified (human review) | When only criteria change (same SLI, same queries), preserve comparable_from_version. |
| `api/tests/quality_gate/evaluation_engine/test_regeneration.py` | `test_indicator_key_added_preserves_baseline` | unclassified (human review) | Adding a new indicator preserves baselines for existing indicators. |
| `api/tests/quality_gate/evaluation_engine/test_regeneration.py` | `test_indicator_key_removed_breaks_baseline` | unclassified (human review) | Removing an indicator key counts as query change. |
| `api/tests/quality_gate/evaluation_engine/test_regeneration.py` | `test_mixed_scenario` | unclassified (human review) | Mixed: add, update, deactivate in one plan. |
| `api/tests/quality_gate/evaluation_engine/test_regeneration.py` | `test_new_rows_added` | unclassified (human review) | New gen_variables rows appear in to_create. |
| `api/tests/quality_gate/evaluation_engine/test_regeneration.py` | `test_rows_removed` | unclassified (human review) | Removed gen_variables rows appear in to_deactivate. |
| `api/tests/quality_gate/evaluation_engine/test_regeneration.py` | `test_sli_version_bump_different_queries_breaks_baseline` | unclassified (human review) | SLI version bump with changed queries breaks baseline. |
| `api/tests/quality_gate/evaluation_engine/test_regeneration.py` | `test_sli_version_bump_same_queries_preserves` | unclassified (human review) | SLI version bump with identical queries preserves baseline. |
| `api/tests/quality_gate/evaluation_engine/test_regeneration.py` | `test_template_variables_changed_breaks_baseline` | unclassified (human review) | Changed template variables break baseline. |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_empty_pass_threshold_list_is_informational` | unclassified (human review) | Empty pass_threshold list must be treated same as no pass criteria. |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_key_sli_failure_flagged` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_key_sli_pass_not_flagged` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_objective_fails` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_objective_missing_metric_is_error` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_objective_no_pass_threshold_is_informational` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_objective_passes` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_objective_warns` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_sign_without_pct_relative_scoring` | unclassified (human review) | <=+10 without % treated as relative (baseline + 10), matching Go behaviour. |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_total_score_all_pass` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_total_score_key_sli_fails_regardless_of_score` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_total_score_no_pass_threshold_returns_pass_100` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_total_score_warning_band` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring.py` | `test_total_score_warning_result` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_scoring_edge_cases.py` | `test_all_info_objectives_result_is_pass` | unclassified (human review) | When all objectives are INFO, maximum is 0 and result is PASS with 100% score. |
| `api/tests/quality_gate/evaluation_engine/test_scoring_edge_cases.py` | `test_evaluate_all_info_objectives` | unclassified (human review) | All objectives are info-only: result should be pass. |
| `api/tests/quality_gate/evaluation_engine/test_scoring_edge_cases.py` | `test_evaluate_mixed_info_and_scored` | unclassified (human review) | Mix of info-only and scored objectives: only scored contribute to final score. |
| `api/tests/quality_gate/evaluation_engine/test_scoring_edge_cases.py` | `test_objective_with_no_criteria_none_value` | unclassified (human review) | INFO objective with None value still returns INFO (not FAIL). |
| `api/tests/quality_gate/evaluation_engine/test_scoring_edge_cases.py` | `test_objective_with_no_criteria_returns_info` | unclassified (human review) | Objective with neither pass nor warning criteria is informational only. |
| `api/tests/quality_gate/evaluation_engine/test_scoring_edge_cases.py` | `test_objective_with_only_warning_threshold_returns_info` | unclassified (human review) | Objective with warning_threshold but no pass_threshold returns INFO status. |
| `api/tests/quality_gate/evaluation_engine/test_slo_builder.py` | `test_build_minimal_slo` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_slo_builder.py` | `test_build_slo_comparison_defaults` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_slo_builder.py` | `test_build_slo_comparison_overridden` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_slo_builder.py` | `test_empty_objectives_raises` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_slo_builder.py` | `test_invalid_comparison_raises` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_slo_builder.py` | `test_objective_defaults` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_slo_builder.py` | `test_score_defaults` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_slo_builder.py` | `test_score_overridden` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables.py` | `test_build_variables_arbitrary_metadata_passthrough` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables.py` | `test_build_variables_evaluation_name` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables.py` | `test_build_variables_evaluation_name_substitution` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables.py` | `test_build_variables_merges_metadata` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables.py` | `test_build_variables_start_end` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables.py` | `test_no_variables_returns_unchanged` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables.py` | `test_substitute_slo_variables_replaces_in_yaml` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables.py` | `test_substitutes_multiple_variables` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables.py` | `test_substitutes_single_variable` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables.py` | `test_unresolved_variable_raises` | unclassified (human review) |  |
| `api/tests/quality_gate/evaluation_engine/test_variables_edge_cases.py` | `test_build_variables_empty_string_asset_name_omitted` | unclassified (human review) | When asset_name is empty string (falsy), $asset_name is not added. |
| `api/tests/quality_gate/evaluation_engine/test_variables_edge_cases.py` | `test_build_variables_none_asset_name_omitted` | unclassified (human review) | When asset_name is None, $asset_name is not added to variables. |
| `api/tests/quality_gate/evaluation_engine/test_variables_edge_cases.py` | `test_dollar_sign_not_followed_by_identifier` | unclassified (human review) | A bare $ not followed by an identifier should be left as-is. |
| `api/tests/quality_gate/evaluation_engine/test_variables_edge_cases.py` | `test_metadata_key_does_not_shadow_reserved_asset_name` | unclassified (human review) | User metadata key 'asset_name' should not shadow built-in $asset_name. |
| `api/tests/quality_gate/evaluation_engine/test_variables_edge_cases.py` | `test_multiple_occurrences_of_same_variable` | unclassified (human review) | Same $variable used twice should both be replaced. |
| `api/tests/quality_gate/evaluation_engine/test_variables_edge_cases.py` | `test_reserved_variable_wins_when_metadata_empty` | unclassified (human review) | When metadata does not contain the key, the built-in variable is used. |
| `api/tests/quality_gate/evaluation_engine/test_variables_edge_cases.py` | `test_special_characters_in_variable_value` | unclassified (human review) | Variable value with regex special chars (brackets, dots) should be literal-substituted. |
| `api/tests/quality_gate/evaluation_engine/test_variables_edge_cases.py` | `test_unresolved_variable_in_query_raises` | unclassified (human review) | Query with $undefined_var raises UnresolvedVariableError. |
| `api/tests/quality_gate/shared/test_params.py` | `test_eval_create_params_optional_fields` | unclassified (human review) |  |
| `api/tests/quality_gate/shared/test_params.py` | `test_eval_create_params_required_fields` | unclassified (human review) |  |
| `api/tests/quality_gate/shared/test_params.py` | `test_eval_create_params_requires_evaluation_id` | unclassified (human review) |  |
| `api/tests/quality_gate/shared/test_schemas.py` | `test_evaluate_batch_request_by_asset` | unclassified (human review) |  |
| `api/tests/quality_gate/shared/test_schemas.py` | `test_evaluate_batch_request_by_date` | unclassified (human review) |  |
| `api/tests/quality_gate/shared/test_schemas.py` | `test_evaluate_batch_response` | unclassified (human review) |  |
| `api/tests/quality_gate/shared/test_schemas.py` | `test_evaluate_single_request_schema` | unclassified (human review) |  |
| `api/tests/quality_gate/shared/test_schemas.py` | `test_evaluate_single_response_schema` | unclassified (human review) |  |
| `api/tests/quality_gate/test_router.py` | `test_evaluations_accepts_from_to_without_date` | unclassified (human review) |  |
| `api/tests/quality_gate/test_router.py` | `test_evaluations_rejects_date_with_from` | unclassified (human review) |  |
| `api/tests/quality_gate/test_router.py` | `test_evaluations_rejects_date_with_to` | unclassified (human review) |  |
| `api/tests/quality_gate/test_router.py` | `test_trend_rejects_asset_name_without_slo_name` | unclassified (human review) |  |
| `api/tests/quality_gate/test_router.py` | `test_trend_rejects_both_eval_id_and_asset_name` | unclassified (human review) |  |
| `api/tests/quality_gate/test_router.py` | `test_trend_rejects_eval_id_combined_with_asset_name` | unclassified (human review) |  |
| `api/tests/quality_gate/test_router.py` | `test_trend_rejects_neither_eval_id_nor_asset_name` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/execution/test_adapter_client.py` | `test_creates_own_client_when_none_injected` | unclassified (human review) | When no http_client is given, _http_client is None and timeout is stored. |
| `api/tests/quality_gate/workflows/execution/test_adapter_client.py` | `test_uses_injected_client` | unclassified (human review) | When an external httpx.AsyncClient is provided, query() uses it directly. |
| `api/tests/quality_gate/workflows/execution/test_baselines.py` | `test_resolve_baselines_aggregates_per_metric` | unclassified (human review) | Collects values from baseline evals and aggregates with avg. |
| `api/tests/quality_gate/workflows/execution/test_baselines.py` | `test_resolve_baselines_no_comparisons` | unclassified (human review) | Returns empty when number_of_comparison_results <= 0. |
| `api/tests/quality_gate/workflows/execution/test_baselines.py` | `test_resolve_baselines_returns_compared_ids` | unclassified (human review) | compared_eval_ids list matches baseline eval IDs. |
| `api/tests/quality_gate/workflows/execution/test_baselines.py` | `test_resolve_baselines_skips_none_values` | unclassified (human review) | None indicator values are excluded from aggregation. |
| `api/tests/quality_gate/workflows/execution/test_evaluation_helpers.py` | `test_build_eval_variables_empty_inputs` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/execution/test_evaluation_helpers.py` | `test_build_eval_variables_merge_priority` | unclassified (human review) | Variables merge with correct priority: reserved < asset.variables < asset.tags < slo < eval. |
| `api/tests/quality_gate/workflows/execution/test_evaluation_helpers.py` | `test_build_eval_variables_none_inputs` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/execution/test_executor_helpers.py` | `test_load_definitions_sli_name_missing` | unclassified (human review) | Raises DefinitionLoadError when evaluation has no sli_name. |
| `api/tests/quality_gate/workflows/execution/test_executor_helpers.py` | `test_load_definitions_sli_not_found` | unclassified (human review) | Raises DefinitionLoadError when SLI definition is not in the database. |
| `api/tests/quality_gate/workflows/execution/test_executor_helpers.py` | `test_load_definitions_sli_version_missing` | unclassified (human review) | Raises DefinitionLoadError when evaluation has no sli_version. |
| `api/tests/quality_gate/workflows/execution/test_executor_helpers.py` | `test_load_definitions_slo_name_missing` | unclassified (human review) | Raises DefinitionLoadError when evaluation has no slo_name. |
| `api/tests/quality_gate/workflows/execution/test_executor_helpers.py` | `test_load_definitions_slo_not_found` | unclassified (human review) | Raises DefinitionLoadError when SLO definition is not in the database. |
| `api/tests/quality_gate/workflows/execution/test_executor_helpers.py` | `test_load_definitions_slo_version_missing` | unclassified (human review) | Raises DefinitionLoadError when evaluation has no slo_version. |
| `api/tests/quality_gate/workflows/execution/test_executor_helpers.py` | `test_load_definitions_success` | unclassified (human review) | Successful load returns (slo_def, sli_def) tuple. |
| `api/tests/quality_gate/workflows/execution/test_executor_helpers.py` | `test_variable_merge_priority` | unclassified (human review) | Variables merge with correct priority: reserved < asset.variables < asset.tags < slo.variables < eval.variables. |
| `api/tests/quality_gate/workflows/execution/test_executor_phases.py` | `test_fetch_and_evaluate_returns_none_on_adapter_failure` | unclassified (human review) | Phase 2 returns None when adapter raises ConnectError. |
| `api/tests/quality_gate/workflows/execution/test_executor_phases.py` | `test_fetch_and_evaluate_returns_result` | unclassified (human review) | Phase 2 returns a FetchAndEvaluateResult on success. |
| `api/tests/quality_gate/workflows/execution/test_executor_phases.py` | `test_load_snapshot_marks_running_and_returns_snapshot` | unclassified (human review) | Phase 1 marks running and returns an EvaluationSnapshot with correct fields. |
| `api/tests/quality_gate/workflows/execution/test_executor_phases.py` | `test_load_snapshot_returns_none_for_already_completed` | unclassified (human review) | Phase 1 returns None when eval is already completed. |
| `api/tests/quality_gate/workflows/execution/test_executor_phases.py` | `test_load_snapshot_returns_none_for_missing_eval` | unclassified (human review) | Phase 1 returns None when eval not found in the database. |
| `api/tests/quality_gate/workflows/execution/test_executor_phases.py` | `test_write_results_commits_eval_and_indicators` | unclassified (human review) | Phase 3a calls mark_completed and bulk_insert (no sli_values). |
| `api/tests/quality_gate/workflows/execution/test_executor_phases.py` | `test_write_sli_values_phase_writes_to_hypertable` | unclassified (human review) | Phase 3b writes SLI values via SLIValueRepository. |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_adapter_failure_marks_failed` | unclassified (human review) | fetch_and_evaluate returns None -> mark_failed called. |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_definition_load_error_marks_failed` | unclassified (human review) | _load_definitions raises DefinitionLoadError -> mark_failed called. |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_finalize_run_job_completes_parent` | unclassified (human review) | finalize_if_all_done returns finalized run -> logged. |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_finalize_run_job_noop_when_children_pending` | unclassified (human review) | finalize_if_all_done returns None -> no logging, still commits. |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_finalize_run_job_warms_heatmap_column_cache_when_redis_available` | unclassified (human review) | When finalize succeeds and Redis is configured, the warm helper fires |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_happy_path_three_phases` | unclassified (human review) | Verify 3+ sessions created, each committed, finalize job enqueued. |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_predecessor_defers_job` | unclassified (human review) | Predecessor check returns True -> job re-enqueued, no phases run. |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_snapshot_none_skips_remaining_phases` | unclassified (human review) | load_evaluation_snapshot returns None -> no further phases. |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_sweeper_cron_seconds_15` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_sweeper_cron_seconds_30` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_sweeper_cron_seconds_5` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_sweeper_cron_seconds_60` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_sweeper_cron_seconds_rejects_non_divisor` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/execution/test_queue.py` | `test_worker_settings_registers_sweeper_job` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py` | `test_cell_aggregation_from_job_stats` | unclassified (human review) | Aggregation mode is extracted from sli_metadata in job_stats. |
| `api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py` | `test_cell_aggregation_none_when_no_metadata` | unclassified (human review) | Aggregation is None when job_stats has no sli_metadata. |
| `api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py` | `test_cell_carries_indicator_detail` | unclassified (human review) | HeatmapCellGrouped includes value, weight, targets from indicator row + objective. |
| `api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py` | `test_composite_row_defaults` | unclassified (human review) | Composite row HeatmapSummaryCell uses defaults for new fields. |
| `api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py` | `test_has_notes_defaults_to_false_when_noted_run_ids_omitted` | unclassified (human review) | When noted_run_ids is not provided, every column has has_notes=False. |
| `api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py` | `test_has_notes_marks_columns_present_in_noted_set` | unclassified (human review) | Columns whose run id is in noted_run_ids get has_notes=True; others False. |
| `api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py` | `test_summary_carries_slo_sli_versions` | unclassified (human review) | HeatmapSummaryCell includes SLO and SLI versions from the evaluation. |
| `api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py` | `test_summary_carries_thresholds_and_metadata` | unclassified (human review) | HeatmapSummaryCell includes pass/warning thresholds, sli_metadata, invalidation. |
| `api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py` | `test_summary_invalidated_flag` | unclassified (human review) | Invalidated SLO evaluation propagates to summary cell. |
| `api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py` | `test_summary_versions_default_to_none` | unclassified (human review) | HeatmapSummaryCell version fields default to None when not set. |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_annotations_sorted_by_created_at` | unclassified (human review) | Annotations in detail response must be sorted by created_at ascending. |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_combined_invalidated_and_overridden` | unclassified (human review) | Both invalidated and override fields can coexist. |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_compared_evaluation_ids` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_empty_indicator_results` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_filters_hidden_annotations` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_from_orm_rows` | unclassified (human review) | build_detail works with ORM indicator rows (new path). |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_invalidated_evaluation` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_latest_annotation_is_most_recent` | unclassified (human review) | latest_annotation in detail should be the most recent visible annotation. |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_null_job_stats` | unclassified (human review) | When job_stats is None, original_score is None and compared_evaluation_ids is empty. |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_overridden_evaluation` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_sli_metadata_from_job_stats` | unclassified (human review) | sli_metadata from job_stats appears in the detail response. |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_sli_metadata_none_when_absent` | unclassified (human review) | sli_metadata is None when job_stats has no sli_metadata key. |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_standard_evaluation` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_uses_stored_targets` | unclassified (human review) | When row has stored targets JSONB, presenter uses them instead of resolve_targets. |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_detail_with_annotations` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_summary_from_orm_rows` | unclassified (human review) | build_summary works with ORM indicator rows (new path). |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_summary_no_pass_targets_in_failure` | unclassified (human review) | Failing indicator without pass_threshold -> threshold defaults to empty string. |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_summary_original_score_from_job_stats` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_summary_standard_evaluation` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_summary_with_annotation_count` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter.py` | `test_build_summary_with_failures` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter_fragment_builder.py` | `test_assemble_grouped_response_merges_fragments_by_slo_name` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter_fragment_builder.py` | `test_assemble_grouped_response_orders_slos_alphabetically` | unclassified (human review) | Stable alphabetical ordering required so cache=true and cache=false |
| `api/tests/quality_gate/workflows/presentation/test_presenter_fragment_builder.py` | `test_build_column_fragment_criteria_scoped_per_row_not_hoisted` | unclassified (human review) | Two rows under the same SLO with DIFFERENT objectives (simulating an |
| `api/tests/quality_gate/workflows/presentation/test_presenter_fragment_builder.py` | `test_build_column_fragment_invalidated_slo_collapses_result_to_invalidated` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_presenter_fragment_builder.py` | `test_build_column_fragment_parses_each_criteria_once` | unclassified (human review) | Parse cache: a run with 6 cells under one objective should parse the |
| `api/tests/quality_gate/workflows/presentation/test_presenter_fragment_builder.py` | `test_build_column_fragment_preserves_slo_and_sli_versions` | unclassified (human review) | Regression guard: HeatmapSummaryCell.slo_version and sli_version must be |
| `api/tests/quality_gate/workflows/presentation/test_presenter_fragment_builder.py` | `test_build_column_fragment_returns_one_fragment_per_run` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_target_resolver.py` | `test_empty_criteria_returns_empty` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_target_resolver.py` | `test_fixed_threshold_not_violated` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_target_resolver.py` | `test_fixed_threshold_violated` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_target_resolver.py` | `test_none_criteria_returns_none` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_target_resolver.py` | `test_null_value_always_violated` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_target_resolver.py` | `test_relative_no_percent_sign` | unclassified (human review) | <=+50 is parsed as <=+50% (relative percent) by the engine — no separate 'absolute' mode. |
| `api/tests/quality_gate/workflows/presentation/test_target_resolver.py` | `test_relative_percent_not_violated` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/presentation/test_target_resolver.py` | `test_relative_percent_violated` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_re_evaluation_service.py` | `test_request_accepts_from_baseline` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_re_evaluation_service.py` | `test_request_accepts_from_date` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_re_evaluation_service.py` | `test_request_accepts_from_evaluation_id` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_re_evaluation_service.py` | `test_request_rejects_multiple_scopes` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_re_evaluation_service.py` | `test_request_requires_exactly_one_scope` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_reeval_pin_conflict.py` | `test_error_is_exception` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_reeval_pin_conflict.py` | `test_error_stores_pin_details` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_reeval_pin_conflict.py` | `test_pin_strategy_ignore_pin` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_reeval_pin_conflict.py` | `test_pin_strategy_invalid_value_rejected` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_reeval_pin_conflict.py` | `test_pin_strategy_none_by_default` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/re_evaluation/test_reeval_pin_conflict.py` | `test_pin_strategy_skip_to_pin` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/trigger/test_resolve_all_slos.py` | `test_collects_from_slo_assignments` | unclassified (human review) | Assignments (direct + via group) are returned sorted. |
| `api/tests/quality_gate/workflows/trigger/test_resolve_all_slos.py` | `test_deduplicates_same_slo_from_multiple_assignments` | unclassified (human review) | The assignment_repo already deduplicates by precedence; result has distinct names. |
| `api/tests/quality_gate/workflows/trigger/test_resolve_all_slos.py` | `test_no_assignments_returns_empty` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/trigger/test_resolve_all_slos.py` | `test_passes_group_ids_to_repo` | unclassified (human review) | group_ids are forwarded to the assignment repo. |
| `api/tests/quality_gate/workflows/trigger/test_trigger_resolver.py` | `test_resolve_all_slos_dedup_by_assignment_repo` | unclassified (human review) | resolve_all_slos_for_asset trusts the assignment_repo's dedup — each name appears once. |
| `api/tests/quality_gate/workflows/trigger/test_trigger_resolver.py` | `test_resolve_all_slos_for_asset` | unclassified (human review) | resolve_all_slos_for_asset returns sorted SLO names from assignment_repo. |
| `api/tests/quality_gate/workflows/trigger/test_trigger_resolver.py` | `test_resolve_no_assignment_raises` | unclassified (human review) | When no assignment exists, raise SLONotConfiguredError. |
| `api/tests/quality_gate/workflows/trigger/test_trigger_resolver.py` | `test_resolve_single_trigger` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/trigger/test_trigger_resolver.py` | `test_resolve_single_trigger_asset_not_found` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/trigger/test_trigger_resolver.py` | `test_trigger_context_includes_display_name` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/trigger/test_trigger_resolver.py` | `test_trigger_context_includes_slo_definition_id` | unclassified (human review) | TriggerContext carries the slo_definition_id FK. |
| `api/tests/quality_gate/workflows/trigger/test_trigger_service.py` | `test_trigger_evaluate_asset_not_found` | unclassified (human review) |  |
| `api/tests/quality_gate/workflows/trigger/test_trigger_service.py` | `test_trigger_evaluate_enqueues_per_child` | unclassified (human review) | One job is enqueued per SLO evaluation child. |
| `api/tests/quality_gate/workflows/trigger/test_trigger_service.py` | `test_trigger_evaluate_happy_path` | unclassified (human review) | trigger_evaluate resolves SLOs, creates run + children, enqueues jobs. |
| `api/tests/quality_gate/workflows/trigger/test_trigger_service.py` | `test_trigger_evaluate_no_slos` | unclassified (human review) | No SLO assignments raises EvaluationError. |
| `api/tests/quality_gate/workflows/trigger/test_trigger_service.py` | `test_trigger_evaluate_skips_unresolvable_slos` | unclassified (human review) | SLOs that fail resolution are skipped; remaining are still created. |
| `api/tests/sli_registry/db/test_comparable_from_version.py` | `test_sli_explicit_comparable_from_version` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_comparable_from_version.py` | `test_sli_first_version_defaults_to_one` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_comparable_from_version.py` | `test_sli_second_version_defaults_to_previous` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_comparable_from_version.py` | `test_slo_explicit_comparable_from_version` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_comparable_from_version.py` | `test_slo_first_version_defaults_to_one` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_comparable_from_version.py` | `test_slo_second_version_defaults_to_previous` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_create_first_version` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_create_increments_version` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_create_with_adapter_type` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_deactivate_hides_from_get_latest` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_get_latest_returns_highest_version` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_get_latest_returns_none_for_unknown` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_get_tag_keys` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_get_tag_values` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_get_version_returns_specific` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_list_all_filters_by_adapter_type` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_list_all_filters_by_tag` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_list_all_returns_latest_per_name` | unclassified (human review) |  |
| `api/tests/sli_registry/db/test_sli_repository.py` | `test_list_versions_newest_first` | unclassified (human review) |  |
| `api/tests/sli_registry/test_params.py` | `test_sli_create_params_full` | unclassified (human review) |  |
| `api/tests/sli_registry/test_params.py` | `test_sli_create_params_minimal` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_aggregated_mode_accepts_string_methods` | unclassified (human review) | Pydantic coerces plain strings to AggregationMethod enum values. |
| `api/tests/sli_registry/test_schemas.py` | `test_aggregated_mode_all_methods_valid` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_aggregated_mode_empty_methods_rejected` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_aggregated_mode_invalid_method_rejected` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_aggregated_mode_valid` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_aggregated_mode_with_indicators_rejected` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_aggregated_mode_without_interval_rejected` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_aggregated_mode_without_methods_rejected` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_aggregated_mode_without_query_template_rejected` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_enum_has_ten_members` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_invalid_mode_rejected` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_raw_mode_default` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_raw_mode_with_aggregated_fields_rejected` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_raw_mode_with_indicators_valid` | unclassified (human review) |  |
| `api/tests/sli_registry/test_schemas.py` | `test_raw_mode_without_indicators_rejected` | unclassified (human review) |  |
| `api/tests/slo_groups/db/test_slo_groups.py` | `test_create_group_generates_slos` | unclassified (human review) | Creating a group generates one SLO per gen_variable row. |
| `api/tests/slo_groups/db/test_slo_groups.py` | `test_create_group_name_collision` | unclassified (human review) | Creating a group that would generate an SLO colliding with existing name returns 409. |
| `api/tests/slo_groups/db/test_slo_groups.py` | `test_create_group_rejects_non_template` | unclassified (human review) | A group referencing a standard SLO (not template kind) is rejected with 422. |
| `api/tests/slo_groups/db/test_slo_groups.py` | `test_deactivate_group_cascades` | unclassified (human review) | Deleting a group deactivates it and its generated SLOs. |
| `api/tests/slo_groups/db/test_slo_groups.py` | `test_extract_slo` | unclassified (human review) | Extracting a generated SLO creates a standalone copy and shrinks the group. |
| `api/tests/slo_groups/db/test_slo_groups.py` | `test_list_groups_tag_filter` | unclassified (human review) | Listing groups with tag filter returns only matching groups. |
| `api/tests/slo_groups/db/test_slo_groups.py` | `test_update_group_add_row` | unclassified (human review) | Updating gen_variables to add a row creates a new generated SLO. |
| `api/tests/slo_groups/db/test_slo_groups.py` | `test_update_group_remove_row` | unclassified (human review) | Updating gen_variables to remove a row deactivates the corresponding SLO. |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_create_first_version` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_create_second_version_increments` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_create_slo_rejects_invalid_indicator` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_create_slo_with_sli_reference` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_create_with_display_name_stores_and_retrieves` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_create_with_variables` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_create_without_display_name_defaults_to_none` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_deactivate_hides_from_get_latest` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_get_latest_nonexistent_returns_none` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_get_latest_returns_highest_version` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_get_tag_keys` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_get_version_specific` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_list_all_filters_by_tag` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_list_slos_filter_by_kind` | unclassified (human review) |  |
| `api/tests/slo_registry/db/test_slo_repository.py` | `test_list_versions_newest_first` | unclassified (human review) |  |
| `api/tests/slo_registry/test_params.py` | `test_slo_create_params_full` | unclassified (human review) |  |
| `api/tests/slo_registry/test_params.py` | `test_slo_create_params_minimal` | unclassified (human review) |  |
| `api/tests/slo_registry/test_params.py` | `test_slo_objective_params_defaults` | unclassified (human review) |  |
| `api/tests/slo_registry/test_service.py` | `test_slo_test_accepts_valid_request_shape` | unclassified (human review) | Valid shape should not get 422 for request validation. |
| `api/tests/slo_registry/test_service.py` | `test_slo_test_rejects_empty_objectives` | unclassified (human review) |  |
| `api/tests/slo_registry/test_service.py` | `test_slo_test_rejects_missing_required_fields` | unclassified (human review) |  |
| `api/tests/slo_registry/test_validate.py` | `test_validate_custom_score_thresholds` | unclassified (human review) |  |
| `api/tests/slo_registry/test_validate.py` | `test_validate_empty_objectives` | unclassified (human review) |  |
| `api/tests/slo_registry/test_validate.py` | `test_validate_invalid_criteria_string` | unclassified (human review) |  |
| `api/tests/slo_registry/test_validate.py` | `test_validate_missing_objectives_field` | unclassified (human review) |  |
| `api/tests/slo_registry/test_validate.py` | `test_validate_valid_slo` | unclassified (human review) |  |
| `api/tests/test_config.py` | `test_async_db_url_format` | unclassified (human review) |  |
| `api/tests/test_config.py` | `test_cache_url_includes_password` | unclassified (human review) |  |
| `api/tests/test_config.py` | `test_config_loads_from_yaml` | unclassified (human review) |  |
| `api/tests/test_config.py` | `test_env_overrides_yaml` | unclassified (human review) |  |
| `api/tests/test_config.py` | `test_missing_config_file_uses_defaults` | unclassified (human review) |  |
| `api/tests/test_config.py` | `test_queue_sweeper_accepts_valid_interval` | unclassified (human review) | Interval=5 (a divisor of 60) is accepted. |
| `api/tests/test_config.py` | `test_queue_sweeper_defaults` | unclassified (human review) | Sweeper config has sane defaults when not present in YAML. |
| `api/tests/test_config.py` | `test_queue_sweeper_rejects_invalid_interval` | unclassified (human review) | Interval=45 (not a divisor of 60) raises at settings construction. |
| `api/tests/test_config.py` | `test_queue_sweeper_rejects_zero_batch_limit` | unclassified (human review) | batch_limit=0 raises. |
| `api/tests/test_db_imports.py` | `test_annotation_uses_slo_evaluation_id` | unclassified (human review) |  |
| `api/tests/test_db_imports.py` | `test_asset_group_link_uses_renamed_fk_cols` | unclassified (human review) |  |
| `api/tests/test_db_imports.py` | `test_asset_group_member_uses_asset_group_id` | unclassified (human review) |  |
| `api/tests/test_db_imports.py` | `test_db_session_imports` | unclassified (human review) | Verify the db session module is importable and exposes expected names. |
| `api/tests/test_db_imports.py` | `test_evaluation_batch_removed` | unclassified (human review) |  |
| `api/tests/test_db_imports.py` | `test_evaluation_run_model_exists` | unclassified (human review) |  |
| `api/tests/test_db_imports.py` | `test_indicator_result_uses_slo_evaluation_id` | unclassified (human review) |  |
| `api/tests/test_db_imports.py` | `test_orm_models_importable` | unclassified (human review) | Verify ORM models import and register expected table names. |
| `api/tests/test_db_imports.py` | `test_sli_value_uses_slo_evaluation_id` | unclassified (human review) |  |
| `api/tests/test_db_imports.py` | `test_slo_evaluation_model_exists` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_all_body_models_inherit_strict_input` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_annotation_read_embeds_category` | unclassified (human review) | UI reads category.color / category.show_on_graph directly off AnnotationRead, |
| `api/tests/test_schema_contracts.py` | `test_annotation_read_has_hidden_fields` | unclassified (human review) | Soft-delete surface: hidden_at filters the note out of active lists, |
| `api/tests/test_schema_contracts.py` | `test_annotation_read_has_note_group_fields` | unclassified (human review) | Per-SLO re-eval groups multiple annotations under a shared note_group_id; |
| `api/tests/test_schema_contracts.py` | `test_annotation_read_has_tags` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_asset_create_has_tags` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_asset_read_has_tags` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_asset_read_has_variables` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_asset_snapshot_is_typed_model` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_category_color_enum_matches_ui_palette` | unclassified (human review) | ui/src/features/note-categories/palette.ts defines exactly these eight |
| `api/tests/test_schema_contracts.py` | `test_category_create_rejects_unknown_fields` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_category_read_color_is_enum` | unclassified (human review) | Colour is a fixed enum (not a free-form hex) so the UI palette maps |
| `api/tests/test_schema_contracts.py` | `test_category_read_exposes_palette_fields` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_category_update_all_fields_optional` | unclassified (human review) | PATCH endpoint accepts any subset of fields; empty payload is valid. |
| `api/tests/test_schema_contracts.py` | `test_category_update_rejects_unknown_fields` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_comparison_config_accepts_scope_tags` | unclassified (human review) | scope_tags is now a declared field, not a smuggled extra. |
| `api/tests/test_schema_contracts.py` | `test_comparison_config_ignores_unknown_fields` | unclassified (human review) | After dropping extra='allow', unknown fields are silently dropped. |
| `api/tests/test_schema_contracts.py` | `test_create_comparison_is_typed` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_create_method_criteria_is_typed` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_create_tags_is_str_map` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_create_variables_is_str_map` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_datasource_read_excludes_token_value` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_datasource_read_has_has_token` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_datasource_read_has_tags` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_evaluate_request_has_variables` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_evaluation_summary_has_variables` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_heatmap_cell_pass_targets_is_typed` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_heatmap_cell_warning_targets_is_typed` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_heatmap_summary_sli_metadata_is_typed` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_method_criteria_override_accepts_weight_and_key_sli` | unclassified (human review) | weight and key_sli mirror SLOObjectiveIn so template Level-2 |
| `api/tests/test_schema_contracts.py` | `test_method_criteria_override_all_fields_optional` | unclassified (human review) | Empty MethodCriteriaOverride is valid -- all six fields are None by default. |
| `api/tests/test_schema_contracts.py` | `test_method_criteria_override_has_threshold_fields` | unclassified (human review) | MethodCriteriaOverride uses pass_threshold / warning_threshold |
| `api/tests/test_schema_contracts.py` | `test_pass_targets_is_typed_list` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_read_comparison_is_typed` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_read_method_criteria_is_typed` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_read_tags_is_str_map` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_read_variables_is_str_map` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_route_accepts_asset_and_slo_query_params` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_route_registered` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_sli_metadata_value_type_is_typed` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_sli_read_has_tags` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_slo_definition_create_roundtrips_method_criteria` | unclassified (human review) | End-to-end: a template with method_criteria survives Pydantic |
| `api/tests/test_schema_contracts.py` | `test_slo_read_has_tags` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_slo_read_has_variables` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_sloshim_renamed_to_avoid_collision` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_variables_is_str_map` | unclassified (human review) |  |
| `api/tests/test_schema_contracts.py` | `test_warning_targets_is_typed_list` | unclassified (human review) |  |
| `api/tests/test_session_middleware.py` | `test_commit_called_before_response_headers` | unclassified (human review) | Session is committed before http.response.start reaches the client. |
| `api/tests/test_session_middleware.py` | `test_non_http_requests_pass_through` | unclassified (human review) | Non-HTTP scopes (websocket, lifespan) skip session creation entirely. |
| `api/tests/test_session_middleware.py` | `test_rollback_on_endpoint_error` | unclassified (human review) | Session is rolled back when the inner app raises an exception. |
| `api/tests/test_session_middleware.py` | `test_session_closed_even_on_commit_failure` | unclassified (human review) | Session is always closed, even if commit raises. |
| `api/tests/test_session_middleware.py` | `test_session_stored_in_scope_state` | unclassified (human review) | Middleware stores the session in scope['state']['session']. |

## Legend

- **covered-by-pact**: Pact verifies the same endpoint shape. Candidate for removal if the integration test adds no business-logic value beyond shape.
- **api-shape-check (candidate for schemathesis coverage)**: Asserts status codes or response shapes. Likely already covered by Schemathesis — candidate for removal.
- **business-logic / db-state (keep)**: Exercises DB state, multi-step sequences, or computed values. Keep.
- **unclassified (human review)**: Could not be auto-classified. Requires reading the test to decide.

## Next step

A human reviews every row, deletes the rows marked for removal, and expands the "keep" rows where business-logic assertions are thin.

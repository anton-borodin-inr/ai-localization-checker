def test_matching_reads_every_golden_case(golden_case, golden_matches):
    result = golden_matches
    expected = golden_case["expected"]
    assert len(result.matches) == expected["tp"]
    assert len(result.unmatched_finding_indices) == expected["fp"]
    assert len(result.unmatched_label_indices) == expected["fn"]
    assert len(result.duplicate_finding_indices) == expected["duplicates_collapsed"]
    assert len(result.hallucination_indices) == expected["hallucinations"]
    if "matches" in expected:
        assert [
            [
                golden_case["findings"][pair.finding_index]["id"],
                golden_case["labels"][pair.label_index]["id"],
            ]
            for pair in result.matches
        ] == expected["matches"]

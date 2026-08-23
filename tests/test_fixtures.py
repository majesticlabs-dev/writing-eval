import json
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROMPTS_PATH = FIXTURES_DIR / "prompts.sample.jsonl"
REFERENCES_PATH = FIXTURES_DIR / "references.sample.jsonl"
OUTPUTS_DIR = FIXTURES_DIR / "sample_outputs"
OUTPUT_PATHS = [
    OUTPUTS_DIR / "baseline-a.jsonl",
    OUTPUTS_DIR / "baseline-b.jsonl",
    OUTPUTS_DIR / "baseline-c.jsonl",
]
VALID_USE_CASES = {
    "article_section",
    "product_writing",
    "exec_communication",
}


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            assert line.strip(), f"{path}:{line_number} is blank"
            record = json.loads(line)
            assert isinstance(record, dict), f"{path}:{line_number} is not an object"
            records.append(record)
    return records


def assert_unique_ids(records: list[dict], path: Path) -> None:
    ids = [record["id"] for record in records]
    assert len(ids) == len(set(ids)), f"duplicate ids in {path}"


def numeric_suffix(record_id: str) -> str:
    prefix, separator, suffix = record_id.rpartition("-")
    assert prefix and separator and suffix.isdigit(), f"invalid fixture id: {record_id}"
    return suffix


def test_all_jsonl_files_parse_as_json_objects() -> None:
    core_paths = [PROMPTS_PATH, REFERENCES_PATH, *OUTPUT_PATHS]
    discovered_paths = sorted(FIXTURES_DIR.rglob("*.jsonl"))

    for path in discovered_paths:
        records = load_jsonl(path)
        assert records, f"{path} must not be empty"
        assert_unique_ids(records, path)

    for path in core_paths:
        assert path in discovered_paths, f"core fixture missing: {path}"


def test_fixture_jsonl_files_have_no_literal_dash_characters() -> None:
    dashes = {chr(0x2013), chr(0x2014), chr(0x2015)}
    for path in sorted(FIXTURES_DIR.rglob("*.jsonl")):
        text = path.read_text(encoding="utf-8")
        present = sorted(hex(ord(char)) for char in dashes if char in text)
        assert present == [], f"{path} contains literal dash characters: {present}"


def test_prompt_fixture_schema_and_distribution() -> None:
    prompts = load_jsonl(PROMPTS_PATH)
    assert len(prompts) >= 12

    for record in prompts:
        assert set(record) == {"id", "use_case", "prompt"}
        assert isinstance(record["id"], str) and record["id"]
        assert record["use_case"] in VALID_USE_CASES
        assert isinstance(record["prompt"], str) and record["prompt"].strip()

    counts = {
        use_case: sum(record["use_case"] == use_case for record in prompts)
        for use_case in VALID_USE_CASES
    }
    assert all(count >= 4 for count in counts.values())


def test_references_match_prompts_and_have_required_fields() -> None:
    prompts = load_jsonl(PROMPTS_PATH)
    references = load_jsonl(REFERENCES_PATH)
    assert len(references) == len(prompts)

    prompt_suffixes = {numeric_suffix(record["id"]) for record in prompts}
    reference_suffixes = {numeric_suffix(record["id"]) for record in references}
    assert reference_suffixes == prompt_suffixes

    for record in references:
        assert set(record) == {"id", "text"}
        assert isinstance(record["id"], str) and record["id"]
        assert isinstance(record["text"], str) and record["text"].strip()
        sentence_count = sum(record["text"].count(mark) for mark in ".!?")
        assert 2 <= sentence_count <= 4


def test_three_aligned_output_fixtures_have_required_fields() -> None:
    assert len(OUTPUT_PATHS) == 3
    assert all(path.is_file() for path in OUTPUT_PATHS)
    assert sorted(OUTPUTS_DIR.glob("*.jsonl")) == sorted(OUTPUT_PATHS)

    prompts = load_jsonl(PROMPTS_PATH)
    prompt_ids = {record["id"] for record in prompts}

    for path in OUTPUT_PATHS:
        outputs = load_jsonl(path)
        assert len(outputs) == 12
        assert_unique_ids(outputs, path)
        assert {record["id"] for record in outputs} == prompt_ids

        for record in outputs:
            assert set(record) == {"id", "text"}
            assert isinstance(record["id"], str) and record["id"]
            assert isinstance(record["text"], str) and record["text"].strip()


# Distinctive topic markers for prompt-output pairing. Each suffix requires
# those substrings in the prompt, the aligned reference, and every output
# record with the same numeric suffix. A swapped or unrelated record fails.
TOPIC_MARKERS = {
    "001": {"prompt": ("release notes",), "text": ("release notes",)},
    "002": {"prompt": ("product metrics",), "text": ("metric",)},
    "003": {"prompt": ("cancel",), "text": ("cancel",)},
    "004": {"prompt": ("documentation",), "text": ("procedure",)},
    "005": {"prompt": ("time zone",), "text": ("time zone",)},
    "006": {"prompt": ("saved filters",), "text": ("filter",)},
    "007": {"prompt": ("dashboard",), "text": ("source",)},
    "008": {"prompt": ("receipt",), "text": ("receipt",)},
    "009": {"prompt": ("launch", "reliability"), "text": ("launch", "week")},
    "010": {"prompt": ("revenue", "retention"), "text": ("revenue", "retention")},
    "011": {"prompt": ("hiring", "friday"), "text": ("hiring", "friday")},
    "012": {"prompt": ("office expansion",), "text": ("office", "expansion")},
}


def test_fixture_prompt_output_pairing_matches_topics() -> None:
    prompts = {
        numeric_suffix(record["id"]): record for record in load_jsonl(PROMPTS_PATH)
    }
    references = {
        numeric_suffix(record["id"]): record for record in load_jsonl(REFERENCES_PATH)
    }
    outputs_by_suffix = [
        {numeric_suffix(record["id"]): record for record in load_jsonl(path)}
        for path in OUTPUT_PATHS
    ]

    assert set(TOPIC_MARKERS) == set(prompts)
    assert set(TOPIC_MARKERS) == set(references)
    for outputs in outputs_by_suffix:
        assert set(TOPIC_MARKERS) == set(outputs)

    for suffix, markers in TOPIC_MARKERS.items():
        prompt_text = prompts[suffix]["prompt"].casefold()
        for marker in markers["prompt"]:
            assert marker.casefold() in prompt_text, (
                f"prompt {suffix} missing topic marker {marker!r}"
            )

        aligned_texts = [
            references[suffix]["text"],
            *(outputs[suffix]["text"] for outputs in outputs_by_suffix),
        ]
        for text in aligned_texts:
            folded = text.casefold()
            for marker in markers["text"]:
                assert marker.casefold() in folded, (
                    f"fixture {suffix} missing topic marker {marker!r} in aligned text"
                )

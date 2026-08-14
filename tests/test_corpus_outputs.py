"""Corpus prompt and output tests."""

import json
from pathlib import Path
import pytest

from writing_eval.corpus import build_prompt, write_outputs
from tests.helpers_corpus import EM_DASH

@pytest.mark.parametrize(
    "use_case",
    ["article_section", "product_writing", "exec_communication"],
)
def test_build_prompt_mentions_title_and_length_no_dash(use_case: str) -> None:
    sample = {"title": "My Title", "word_count": 250, "use_case": use_case}
    prompt = build_prompt(sample)
    assert "My Title" in prompt
    assert "250" in prompt
    assert EM_DASH not in prompt
    assert chr(0x2013) not in prompt


# --- write_outputs -----------------------------------------------------


def test_write_outputs_schema_and_ascii(tmp_path: Path) -> None:
    holdout = [
        {
            "id": "sample-h1",
            "use_case": "article_section",
            "title": f"Title{EM_DASH}Dash",
            "source_path": "h1.md",
            "text": f"Holdout text with an em dash{EM_DASH}right here.",
            "word_count": 6,
        }
    ]
    eval_set = [
        {
            "id": "sample-e1",
            "use_case": "product_writing",
            "title": "Eval Title",
            "source_path": "e1.md",
            "text": "Eval text goes here.",
            "word_count": 4,
        }
    ]
    out_dir = tmp_path / "out"
    paths = write_outputs(holdout, eval_set, out_dir)

    references_path = paths["references_holdout"]
    eval_path = paths["eval_set"]
    prompts_path = paths["prompts_eval"]

    references_bytes = references_path.read_bytes()
    assert EM_DASH.encode("utf-8") not in references_bytes
    reference_record = json.loads(references_path.read_text(encoding="utf-8").splitlines()[0])
    assert set(reference_record) == {"id", "text", "source", "file"}
    assert reference_record["source"] == "holdout-2.2"
    assert reference_record["file"] == "h1.md"
    assert EM_DASH in reference_record["text"]

    eval_record = json.loads(eval_path.read_text(encoding="utf-8").splitlines()[0])
    assert set(eval_record) == {
        "id",
        "use_case",
        "title",
        "source_path",
        "text",
        "word_count",
    }

    prompt_record = json.loads(prompts_path.read_text(encoding="utf-8").splitlines()[0])
    assert set(prompt_record) == {"id", "use_case", "prompt"}
    assert prompt_record["id"] == "sample-e1"


def test_write_outputs_sorted_by_id(tmp_path: Path) -> None:
    holdout = [
        {
            "id": "sample-b",
            "use_case": "article_section",
            "title": "B",
            "source_path": "b.md",
            "text": "Second sample text right here.",
            "word_count": 5,
        },
        {
            "id": "sample-a",
            "use_case": "article_section",
            "title": "A",
            "source_path": "a.md",
            "text": "First sample text right here.",
            "word_count": 5,
        },
    ]
    out_dir = tmp_path / "out"
    paths = write_outputs(holdout, [], out_dir)
    ids = [
        json.loads(line)["id"]
        for line in paths["references_holdout"].read_text(encoding="utf-8").splitlines()
    ]
    assert ids == ["sample-a", "sample-b"]


def test_write_jsonl_failure_leaves_no_temporary_file(tmp_path: Path) -> None:
    from writing_eval.corpus import _write_jsonl

    path = tmp_path / "out.jsonl"
    with pytest.raises(TypeError):
        _write_jsonl(path, [{"id": object()}])
    assert list(tmp_path.glob(".*")) == []
    assert not path.exists()

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = (
    "price01_aksay_original_protocol_baseline_2026-10-17.json",
    "price01_website_cohort_official_2026-10-18.json",
    "price01_workload_normalization_2026-10-18.json",
    "source_pipeline_policy_v1.json",
    "b2b_oct18_three_new_eis_originals.json",
    "b2bcenter_six_primary_oct18.json",
    "b2b_oct18_b2bcenter_4643484_firstparty.json",
)


def test_runtime_images_package_required_receipts():
    for dockerfile in ("deploy/local/Dockerfile", "deploy/pilot/Dockerfile"):
        content = (ROOT / dockerfile).read_text()
        for name in RECEIPTS:
            assert (ROOT / "docs/roadmap" / name).is_file()
            assert f"docs/roadmap/{name}" in content


def test_overlay_dependency_guard_and_explicit_base():
    dockerfile = (ROOT / "deploy/local/Dockerfile").read_text()
    assert "Overlay dependency mismatch: rebuild full pilot base" in dockerfile
    assert "python -m pip check" in dockerfile
    assert "COPY pyproject.toml /tmp/overlay-pyproject.toml" in dockerfile
    assert "ARVECTUM_LOCAL_BASE_IMAGE" in (ROOT / "deploy/local/compose.macmini.yaml").read_text()

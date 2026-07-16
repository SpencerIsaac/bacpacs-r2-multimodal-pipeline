import json

from Modality_Pipelines.common.analysis_registry import (
    get_analysis_callable,
    list_available_analyses,
    resolve_analysis_spec,
)
from Modality_Pipelines.common.table_registry import (
    get_primary_processed_table,
    get_stage_registry,
    get_supported_modalities,
    get_supported_studies,
    get_table_class,
)


def test_table_registry_exposes_runtime_discovery_helpers():
    assert get_supported_studies() == ["R1", "R2"]
    assert "delsys" in get_supported_modalities("R2")
    assert get_table_class("R1", "R1DelsysProcessed").__name__ == "R1DelsysProcessed"
    assert get_primary_processed_table("R2", "delsys").__name__ == "DelsysProcessed"

    stage_registry = get_stage_registry("R2")
    assert stage_registry["delsys"]["raw_file"] == "DelsysRawFile"
    assert stage_registry["delsys"]["processed"] == ["DelsysProcessed"]


def test_analysis_registry_resolves_study_specific_tables(tmp_path):
    registry_path = tmp_path / "analysis_registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "analyses": {
                    "mock_coactivation": {
                        "modality": "delsys",
                        "input_stage": "processed",
                        "output_table": {
                            "R1": "R1DelsysProcessed",
                            "R2": "DelsysProcessed",
                        },
                        "module": "math",
                        "function": "sqrt",
                        "input_name": "processed_record",
                        "description": "mock dynamic analysis entry",
                    }
                }
            }
        )
    )

    r1_spec = resolve_analysis_spec("R1", "mock_coactivation", registry_path=registry_path)
    r2_spec = resolve_analysis_spec("R2", "mock_coactivation", registry_path=registry_path)

    assert r1_spec.input_table.__name__ == "R1DelsysProcessed"
    assert r1_spec.output_tables[0].__name__ == "R1DelsysProcessed"
    assert r2_spec.input_table.__name__ == "DelsysProcessed"
    assert r2_spec.output_tables[0].__name__ == "DelsysProcessed"
    assert get_analysis_callable(r2_spec)(9) == 3

    rows = list_available_analyses("R2", registry_path=registry_path)
    assert rows == [
        {
            "name": "mock_coactivation",
            "modality": "delsys",
            "description": "mock dynamic analysis entry",
            "module": "math",
            "function": "sqrt",
            "batch_enabled": True,
            "input_table": "DelsysProcessed",
            "output_tables": ["DelsysProcessed"],
        }
    ]

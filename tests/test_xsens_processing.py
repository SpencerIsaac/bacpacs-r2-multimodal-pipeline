from pathlib import Path

import pandas as pd

from Modality_Pipelines.Xsens_Pipeline.process_xsens import _file_path_from_record


def test_xsens_file_path_from_scidb_one_row_dataframe():
    raw_record = pd.DataFrame(
        [
            {
                "file_path": r"Y:\BACPACS R1 - Smart AFO\Subject Data\R1_001\1. Baseline\Xsens\R1_001_BL_xsens_SSV2_noAFO.mvnx"
            }
        ]
    )

    path = _file_path_from_record(raw_record)

    assert isinstance(path, Path)
    assert path.name == "R1_001_BL_xsens_SSV2_noAFO.mvnx"
    assert path.suffix == ".mvnx"
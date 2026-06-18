from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.config_manager import load_config
from backend.core.excel_exporter import export_analysis
from backend.core.excel_reader import read_sheet, standardize_records
from backend.core.field_mapper import auto_map_fields, validate_mapping
from backend.core.patent_ranker import rank_patents
from backend.core.patent_summarizer import summarize_records


def mapping_warnings(mapping: dict[str, str]) -> list[str]:
    warnings = []
    recommended = ["专利名称", "申请号", "公开号", "申请人", "摘要", "法律状态"]
    missing = [field for field in recommended if not mapping.get(field)]
    if missing:
        warnings.append(f"以下推荐字段未映射：{'、'.join(missing)}。结果仍会生成，但建议人工复核。")
    return warnings


async def analyze_xlsx_file(
    file_path: Path,
    sheet_name: str | None,
    requirement: str,
    keyword_analysis: dict[str, Any] | None,
    field_mapping: dict[str, str] | None,
    max_ai_summary: int,
    important_applicants: list[str] | None,
) -> dict[str, Any]:
    if not requirement.strip():
        raise ValueError("请先填写专利检索需求。")

    df = read_sheet(file_path, sheet_name)
    columns = [str(col) for col in df.columns]
    mapping = validate_mapping(field_mapping or auto_map_fields(columns), columns)
    records = standardize_records(df, mapping)
    if not records:
        raise ValueError("未读取到专利记录。")

    config = load_config()
    warnings = mapping_warnings(mapping)
    ranked = rank_patents(
        records,
        requirement,
        keyword_analysis or {},
        config,
        important_applicants or [],
    )
    summarized, summary_warnings = await summarize_records(
        ranked,
        requirement,
        keyword_analysis or {},
        max_ai_summary,
    )
    warnings.extend(summary_warnings)
    output_file, output_filename = export_analysis(
        summarized,
        requirement,
        keyword_analysis or {},
        warnings,
    )
    return {
        "row_count": len(ranked),
        "output_file": output_file,
        "output_filename": output_filename,
        "warnings": warnings,
        "top_records": summarized[:10],
        "mapping": mapping,
    }

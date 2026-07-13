# Glossary

| Term | Meaning |
| --- | --- |
| SOP | Standard Operating Procedure. The human source of truth for operator workflow and conventions. |
| SciStack | Package suite used for database-backed processing, lineage, and stage execution. |
| SciDB | SciStack table/model layer used by the pipeline. |
| DuckDB | Local database engine used for the shared pipeline database file. |
| RawFile table | Database table storing a registered raw-file path and parsed metadata. It does not store the raw signal itself. |
| Processed table | Database table storing first-pass cleaned/structured outputs from a modality processor. |
| Analysis table | Database table storing derived downstream results from processed records. |
| Validation | Read-only scan of raw-file names and folder locations. |
| Registration | Write step that creates RawFile records for valid new files. |
| Dry run | Preview mode that reports what would happen without writing outputs. |
| Overwrite | Explicit option to recompute outputs that already exist. |
| Lineage | Processing history linking source records, functions, configs, and outputs. |
| Registry | Metadata file or Python mapping used to discover tables, stages, or analyses at runtime. |

import csv
from pathlib import Path
from typing import List, Dict
from src.models import ResourceRecord

CSV_COLUMNS = [
    "Identificador", "ARN", "Tipo de recurso", "Região", "Conta da AWS",
    "Aplicação", "CfnResourceType", "LastReportedAt", "Serviço", "Tags"
]

def _read_csv_with_fallback(file_path: Path) -> List[Dict[str, str]]:
    encodings = ["utf-8-sig", "utf-8", "iso-8859-1", "cp1252"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                return list(reader)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Could not decode CSV file {file_path}")

def load_and_deduplicate_csvs(directory_path: str) -> List[ResourceRecord]:
    dir_path = Path(directory_path)
    csv_files = sorted(dir_path.glob("*.csv"))
    
    canonical_map: Dict[str, ResourceRecord] = {}

    for file_path in csv_files:
        rows = _read_csv_with_fallback(file_path)
        for row in rows:
            ident = (row.get("Identificador") or "").strip()
            arn = (row.get("ARN") or "").strip()
            res_type = (row.get("Tipo de recurso") or "").strip()
            region = (row.get("Região") or "").strip()
            account = (row.get("Conta da AWS") or "").strip()
            app_raw = (row.get("Aplicação") or "").strip()
            cfn_type = (row.get("CfnResourceType") or "").strip()
            last_reported = (row.get("LastReportedAt") or "").strip()
            service = (row.get("Serviço") or "").strip()
            tags = (row.get("Tags") or "0").strip()

            key = arn if arn else f"{service}:{res_type}:{region}:{ident}"
            if not key or key == ":::":
                continue

            if key not in canonical_map:
                canonical_map[key] = ResourceRecord(
                    identifier=ident,
                    arn=arn,
                    resource_type=res_type,
                    region=region,
                    aws_account=account,
                    application_raw=app_raw,
                    cfn_resource_type=cfn_type,
                    last_reported_at=last_reported,
                    service=service,
                    tags=tags,
                    source_files=[file_path.name]
                )
            else:
                existing = canonical_map[key]
                if file_path.name not in existing.source_files:
                    existing.source_files.append(file_path.name)
                # Keep latest reported date or more specific info
                if last_reported > existing.last_reported_at:
                    existing.last_reported_at = last_reported
                if existing.tags in ("0", "-") and tags not in ("0", "-", ""):
                    existing.tags = tags
                if not existing.cfn_resource_type or existing.cfn_resource_type == "-":
                    existing.cfn_resource_type = cfn_type

    return list(canonical_map.values())

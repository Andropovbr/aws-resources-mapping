import csv
import re
from pathlib import Path
from typing import List, Dict
from src.models import ResourceRecord

CSV_COLUMNS = [
    "Identificador", "ARN", "Tipo de recurso", "Região", "Conta da AWS",
    "Aplicação", "CfnResourceType", "LastReportedAt", "Serviço", "Tags"
]

OPAQUE_PATTERNS = [
    re.compile(r"^(i|eni|vol|vpc|subnet|sgr|sg|rtb|igw|nat|dopt|acl|eipalloc)-[0-9a-f]{8,32}$", re.IGNORECASE),
    re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE),
    re.compile(r"^Z[0-9A-Z]{10,32}$"),
    re.compile(r"^(applications|attribute-groups)/[0-9a-z]{20,}$", re.IGNORECASE),
]

NAME_COLUMN_CANDIDATES = [
    "name", "nome", "tag:name", "tag:nome", "resourcename", "resource:name", "name tag"
]

def _extract_resource_name(row: Dict[str, str], identifier: str) -> str:
    # 1. Look for explicit column in CSV
    for col_key, col_val in row.items():
        if col_key and col_key.strip().lower() in NAME_COLUMN_CANDIDATES:
            val = (col_val or "").strip()
            if val and val not in ("-", "0"):
                return val

    # 2. Fallback heuristic: friendly identifier if not opaque
    if not identifier:
        return "-"
    if any(p.match(identifier) for p in OPAQUE_PATTERNS):
        return "-"
    return identifier

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
            res_name = _extract_resource_name(row, ident)

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
                    resource_name=res_name,
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
                if existing.resource_name in ("-", "") and res_name not in ("-", ""):
                    existing.resource_name = res_name

    return list(canonical_map.values())

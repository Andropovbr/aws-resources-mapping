import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from src.models import (
    ResourceRecord,
    TopologyComponent,
    ComponentConnection,
    ApplicationTopology,
    TopologyAnalysisResult,
    InventoryReportData
)

LAYER_INGRESS = "Ingresso & Endpoints"
LAYER_COMPUTE = "Computação & Lógica"
LAYER_MESSAGING = "Mensageria & Filas"
LAYER_DATABASE = "Banco de Dados & Cache"
LAYER_STORAGE = "Armazenamento & Apoio"

def load_application_catalog(catalog_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Carrega o catálogo declarativo de aplicações e governança.
    Busca no caminho fornecido ou em catalog/applications.json e applications.json.
    """
    candidates = []
    if catalog_path:
        candidates.append(Path(catalog_path))
    else:
        candidates.append(Path.cwd() / "catalog" / "applications.json")
        candidates.append(Path.cwd() / "applications.json")
        candidates.append(Path(__file__).resolve().parent.parent / "catalog" / "applications.json")

    for path in candidates:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "applications" in data:
                        return data["applications"]
                    elif isinstance(data, dict):
                        return data
            except Exception:
                continue

    return {}

def classify_layer(record: ResourceRecord) -> str:
    """
    Determina a camada funcional do componente com base no serviço AWS e tipos de recurso.
    """
    svc = (record.service or "").lower()
    res_type = (record.resource_type or "").lower()
    cfn_type = (record.cfn_resource_type or "").lower()
    ident = (record.identifier or "").lower()

    # 1. Ingresso & Endpoints
    if (
        "loadbalancer" in res_type
        or "loadbalancer" in cfn_type
        or "targetgroup" in res_type
        or "targetgroup" in cfn_type
        or svc in ("elasticloadbalancing", "apigateway", "cloudfront", "route53")
    ):
        return LAYER_INGRESS

    # 2. Computação & Lógica
    if (
        svc == "lambda"
        or (svc == "ec2" and ("instance" in res_type or "instance" in cfn_type or ident.startswith("i-")))
        or svc in ("ecs", "elasticbeanstalk")
    ):
        return LAYER_COMPUTE

    # 3. Mensageria & Filas
    if svc in ("sqs", "sns") or "event" in svc or "events" in res_type:
        return LAYER_MESSAGING

    # 4. Banco de Dados & Cache
    if (
        svc in ("rds", "dynamodb", "elasticache", "memorydb", "docdb")
        or "cluster" in res_type
        or "dbinstance" in cfn_type
    ):
        return LAYER_DATABASE

    # 5. Armazenamento & Apoio
    if svc in ("s3", "secretsmanager", "efs", "fsx"):
        return LAYER_STORAGE

    # Fallback por serviço
    if svc in ("ec2", "autoscaling"):
        return LAYER_COMPUTE

    return LAYER_STORAGE

def resolve_ownership(
    record: ResourceRecord,
    catalog: Dict[str, Dict[str, Any]],
    inferred_app: str = ""
) -> Tuple[str, Optional[str], str]:
    """
    Determina a Squad, Tech Lead/Owner e Nível de Criticidade seguindo a precedência:
    1. Catálogo Declarativo (match patterns)
    2. Tags nativas do CSV
    3. Mapeamento por inferência de cluster / slug
    4. Fallback padrão
    """
    target_str = f"{record.identifier} {record.arn} {record.tags} {record.application_raw}".lower()

    # 1. Catálogo Declarativo
    for app_id, app_info in catalog.items():
        patterns = app_info.get("match_patterns", [])
        for pat in patterns:
            if pat.lower() in target_str:
                return (
                    app_info.get("squad", "Squad A Definir"),
                    app_info.get("owner"),
                    app_info.get("criticality", "Padrão")
                )

    # 2. Tags do CSV
    tags_lower = (record.tags or "").lower()
    if "squad=" in tags_lower or "team=" in tags_lower:
        match = re.search(r"(?:squad|team)=([^;,\s]+)", tags_lower)
        if match:
            squad_tag = match.group(1).strip()
            return f"Squad {squad_tag.title()}", None, "Padrão"

    # 3. Inferred App / Cluster
    if inferred_app and inferred_app not in ("Não Identificado", "Infraestrutura Compartilhada", "Governança & Segurança"):
        return f"Squad {inferred_app}", None, "Padrão"

    # 4. Fallbacks
    if record.macro_domain == "Governança" or inferred_app == "Governança & Segurança":
        return "Squad Segurança & Governança", None, "Padrão"
    elif record.macro_domain == "Infraestrutura Compartilhada" or inferred_app == "Infraestrutura Compartilhada":
        return "Squad Infraestrutura Cloud", None, "Padrão"

    return "Squad A Definir", None, "Padrão"

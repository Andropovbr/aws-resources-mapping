from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class ResourceRecord:
    identifier: str
    arn: str
    resource_type: str
    region: str
    aws_account: str
    application_raw: str
    cfn_resource_type: str
    last_reported_at: str
    service: str
    tags: str
    source_files: List[str] = field(default_factory=list)
    macro_domain: str = "A Classificar"
    inferred_app: str = "Não Identificado"
    finops_suggestion: str = "Avaliar"
    finops_cost_impact: str = "Baixo/Zero"
    finops_rationale: str = ""

@dataclass
class ApplicationCluster:
    name: str
    slug: str
    resources: List[ResourceRecord] = field(default_factory=list)
    compute_instances: List[str] = field(default_factory=list)
    load_balancers: List[str] = field(default_factory=list)
    target_groups: List[str] = field(default_factory=list)
    databases: List[str] = field(default_factory=list)
    secrets: List[str] = field(default_factory=list)
    storage_buckets: List[str] = field(default_factory=list)

@dataclass
class InventoryReportData:
    account_id: str
    total_resources: int
    unique_arns: int
    regions: Dict[str, int]
    services: Dict[str, int]
    macro_domains: Dict[str, int]
    finops_summary: Dict[str, int]
    clusters: List[ApplicationCluster]
    all_resources: List[ResourceRecord]

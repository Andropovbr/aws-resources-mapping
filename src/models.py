from dataclasses import dataclass, field
from typing import List, Dict, Optional

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
    resource_name: str = "-"
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

@dataclass
class PlaybookGuide:
    playbook_id: str
    title: str
    target_metric: str
    target_resources: List[str]
    console_path: str
    aws_cli_command: str
    decision_criteria: str
    recommended_action: str

@dataclass
class FinOpsOpportunity:
    pillar: str  # "Padrões de Consumo", "Superdimensionamento", "Redução de Custos"
    title: str
    description: str
    evidence_status: str  # "[AÇÃO IMEDIATA]" ou "[NECESSITA ANÁLISE]"
    effort_level: str  # "Baixo (Quick Win)", "Médio", "Alto"
    impact_level: str  # "Alto", "Médio", "Baixo"
    estimated_monthly_savings_usd: Optional[float]
    affected_resources_count: int
    resource_identifiers: List[str] = field(default_factory=list)
    playbook_id: Optional[str] = None

@dataclass
class FinOpsAnalysisResult:
    account_id: str
    total_opportunities: int
    immediate_actions_count: int
    needs_analysis_count: int
    total_estimated_monthly_savings_usd: float
    pillar_consumption_opportunities: List[FinOpsOpportunity]
    pillar_rightsizing_opportunities: List[FinOpsOpportunity]
    pillar_cost_reduction_opportunities: List[FinOpsOpportunity]
    playbooks: List[PlaybookGuide]

@dataclass
class OrphanPlaybookGuide:
    playbook_id: str
    title: str
    category: str
    target_resources: List[str]
    inspection_console_path: str
    inspection_cli_command: str
    decision_criteria: str
    safe_cleanup_cli_command: str
    safety_recommendation: str

@dataclass
class OrphanCandidate:
    category: str
    resource_type: str
    resource_identifier: str
    resource_name: str
    region: str
    status: str
    confidence_rationale: str
    estimated_monthly_waste_usd: float
    playbook_id: str

@dataclass
class OrphanAnalysisResult:
    account_id: str
    total_candidates: int
    confirmed_orphans_count: int
    potential_orphans_count: int
    total_estimated_monthly_waste_usd: float
    categories_breakdown: Dict[str, List[OrphanCandidate]]
    playbooks: List[OrphanPlaybookGuide]


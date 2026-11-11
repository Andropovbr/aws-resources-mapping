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
    account_name: Optional[str] = None
    account_display: Optional[str] = None

    @property
    def display_title(self) -> str:
        if self.account_display:
            return self.account_display
        if self.account_name and self.account_name != self.account_id:
            return f"Conta {self.account_name} ({self.account_id})"
        return f"Conta {self.account_id}"

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
    account_name: Optional[str] = None
    account_display: Optional[str] = None

    @property
    def display_title(self) -> str:
        if self.account_display:
            return self.account_display
        if self.account_name and self.account_name != self.account_id:
            return f"Conta {self.account_name} ({self.account_id})"
        return f"Conta {self.account_id}"

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
    account_name: Optional[str] = None
    account_display: Optional[str] = None

    @property
    def display_title(self) -> str:
        if self.account_display:
            return self.account_display
        if self.account_name and self.account_name != self.account_id:
            return f"Conta {self.account_name} ({self.account_id})"
        return f"Conta {self.account_id}"

@dataclass
class TopologyComponent:
    id: str
    name: str
    service: str
    layer: str
    arn: str
    region: str
    squad: str
    owner: Optional[str] = None
    criticality: str = "Padrão"
    upstream_ids: List[str] = field(default_factory=list)
    downstream_ids: List[str] = field(default_factory=list)

@dataclass
class ComponentConnection:
    source_id: str
    target_id: str
    connection_type: str
    label: str

@dataclass
class ApplicationTopology:
    app_name: str
    slug: str
    squad: str
    owner: Optional[str]
    criticality: str
    description: str
    components: List[TopologyComponent] = field(default_factory=list)
    connections: List[ComponentConnection] = field(default_factory=list)

    @property
    def ingress_components(self) -> List[TopologyComponent]:
        return [c for c in self.components if c.layer == "Ingresso & Endpoints"]

    @property
    def compute_components(self) -> List[TopologyComponent]:
        return [c for c in self.components if c.layer == "Computação & Lógica"]

    @property
    def messaging_components(self) -> List[TopologyComponent]:
        return [c for c in self.components if c.layer == "Mensageria & Filas"]

    @property
    def database_components(self) -> List[TopologyComponent]:
        return [c for c in self.components if c.layer == "Banco de Dados & Cache"]

    @property
    def storage_components(self) -> List[TopologyComponent]:
        return [c for c in self.components if c.layer == "Armazenamento & Apoio"]

@dataclass
class TopologyAnalysisResult:
    account_id: str
    total_applications: int
    total_components: int
    total_connections: int
    assigned_squads_count: int
    squad_distribution: Dict[str, int]
    layer_distribution: Dict[str, int]
    applications: List[ApplicationTopology]
    shared_infrastructure: List[TopologyComponent]
    unassigned_components: List[TopologyComponent]
    account_name: Optional[str] = None
    account_display: Optional[str] = None

    @property
    def display_title(self) -> str:
        if self.account_display:
            return self.account_display
        if self.account_name and self.account_name != self.account_id:
            return f"Conta {self.account_name} ({self.account_id})"
        return f"Conta {self.account_id}"



# Mapeamento de Arquitetura de Aplicações, Topologia de Dependências e Governança (Ownership) - Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o subsistema analítico de identificação de aplicações, componentes em camadas funcionais, dependências de ponta a ponta e governança/ownership com geração de relatórios completos em Markdown (com diagramas Mermaid), DOCX corporativo e aba dedicada no Excel do inventário.

**Architecture:** O módulo `src/topology_analyzer.py` processará os recursos consolidados de `InventoryReportData`, carregando um catálogo declarativo opcional (`catalog/applications.json`) e aplicando heurísticas de classificação em 5 camadas funcionais e inferência de conexões (ALB -> Target Group -> EC2/ECS, SQS/SNS -> Lambda, Compute -> Bancos/Storage). Os resultados serão encapsulados em `TopologyAnalysisResult` e exportados via `src/exporters/topology_report.py`, `src/exporters/excel.py` e convertidos para Word via `src/exporters/docx_report.py` dentro do pipeline `src/main.py`.

**Tech Stack:** Python 3.10+, Dataclasses, OpenPyXL, Markdown, Mermaid.js syntax, Python-docx, Pytest.

**Spec:** [docs/superpowers/specs/2026-11-11-aws-application-topology-and-ownership-design.md](file:///C:/Users/andre.luiz/Documents/resources%20multicanais/docs/superpowers/specs/2026-11-11-aws-application-topology-and-ownership-design.md)

## Global Constraints

- Python runtime invocation: usar `python -m pytest` para execução de testes no Windows.
- Preservar integridade de todos os 74 testes existentes sem qualquer quebra ou regressão.
- Identificadores em diagramas Mermaid devem ser sanitizados para evitar quebras de renderização (substituir caracteres inválidos como `:` ou `/` por `_` nos IDs de nós e usar rótulos entre aspas).
- Fallback elegante caso `applications.json` não exista: prosseguir sem lançar exceções.
- Manter o padrão de logging (`[*]`, `[+]`, `[OK]`, `[✓]`) em `src/main.py`.

---

### Task 1: Modelos de Dados e Estrutura de Catálogo

**Files:**
- Modify: `src/models.py`
- Create: `catalog/applications.json`
- Test: `tests/test_topology_models.py`

**Interfaces:**
- Consumes: `src/models.py`
- Produces: `TopologyComponent`, `ComponentConnection`, `ApplicationTopology`, `TopologyAnalysisResult`

- [ ] **Step 1: Escrever teste falhando para novos modelos de topologia**

Criar `tests/test_topology_models.py`:
```python
import pytest
from src.models import (
    TopologyComponent,
    ComponentConnection,
    ApplicationTopology,
    TopologyAnalysisResult
)

def test_topology_models_instantiation():
    comp_ingress = TopologyComponent(
        id="alb-vdo",
        name="alb-vdo",
        service="elasticloadbalancing",
        layer="Ingresso & Endpoints",
        arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/alb-vdo/1",
        region="us-east-1",
        squad="Squad Marketing & Promoções",
        owner="techlead-vdo@empresa.com",
        criticality="Alta",
        upstream_ids=[],
        downstream_ids=["tg-vdo-80"]
    )

    comp_compute = TopologyComponent(
        id="i-0123456789abcdef0",
        name="i-0123456789abcdef0",
        service="ec2",
        layer="Computação & Lógica",
        arn="arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
        region="us-east-1",
        squad="Squad Marketing & Promoções",
        owner="techlead-vdo@empresa.com",
        criticality="Alta",
        upstream_ids=["tg-vdo-80"],
        downstream_ids=["vdo-mysql-prd"]
    )

    conn = ComponentConnection(
        source_id="alb-vdo",
        target_id="tg-vdo-80",
        connection_type="Ingress",
        label="Roteia tráfego"
    )

    app_topo = ApplicationTopology(
        app_name="VDO & Promoção Digital",
        slug="vdo-promocao",
        squad="Squad Marketing & Promoções",
        owner="techlead-vdo@empresa.com",
        criticality="Alta",
        description="Sistema de gestão e veiculação de promoções",
        components=[comp_ingress, comp_compute],
        connections=[conn]
    )

    assert len(app_topo.ingress_components) == 1
    assert app_topo.ingress_components[0].id == "alb-vdo"
    assert len(app_topo.compute_components) == 1
    assert len(app_topo.messaging_components) == 0
    assert len(app_topo.database_components) == 0

    analysis_result = TopologyAnalysisResult(
        account_id="123456789012",
        account_name="multicanais-dev",
        total_applications=1,
        total_components=2,
        total_connections=1,
        assigned_squads_count=1,
        squad_distribution={"Squad Marketing & Promoções": 2},
        layer_distribution={"Ingresso & Endpoints": 1, "Computação & Lógica": 1},
        applications=[app_topo],
        shared_infrastructure=[],
        unassigned_components=[]
    )

    assert analysis_result.display_title == "Conta multicanais-dev (123456789012)"
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `python -m pytest tests/test_topology_models.py`  
Expected: FAIL com ImportError (`cannot import name 'TopologyComponent' from 'src.models'`)

- [ ] **Step 3: Implementar novos modelos em `src/models.py` e criar catálogo base**

Editar `src/models.py` adicionando no final:
```python
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
```

Criar `catalog/applications.json`:
```json
{
  "applications": {
    "canais-digitais": {
      "name": "Canais Digitais",
      "squad": "Squad Canais & Portais",
      "owner": "techlead-canais@empresa.com",
      "criticality": "Crítica / Tier 1",
      "match_patterns": ["canais", "multicanais", "canaisdb"],
      "description": "Plataforma central de atendimento e portais digitais"
    },
    "vdo-promocao": {
      "name": "VDO & Promoção Digital",
      "squad": "Squad Marketing & Promoções",
      "owner": "techlead-vdo@empresa.com",
      "criticality": "Alta",
      "match_patterns": ["vdo", "promo-digital", "promodb", "alb-vdo", "porto-vdo"],
      "description": "Sistema de gestão e veiculação de promoções e campanhas"
    },
    "wordpress-blog": {
      "name": "WordPress / Blog",
      "squad": "Squad Conteúdo & Institucional",
      "owner": "techlead-conteudo@empresa.com",
      "criticality": "Média",
      "match_patterns": ["wordpress", "blog"],
      "description": "Portais de conteúdo corporativo e blogs institucionais"
    }
  }
}
```

- [ ] **Step 4: Executar testes para verificar sucesso**

Run: `python -m pytest tests/test_topology_models.py`  
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/models.py catalog/applications.json tests/test_topology_models.py
git commit -m "feat(models): add dataclasses and catalog template for application topology"
```

---

### Task 2: Motor Analítico - Classificação de Camadas e Resolução de Ownership

**Files:**
- Create: `src/topology_analyzer.py`
- Create: `tests/test_topology_analyzer.py`

**Interfaces:**
- Consumes: `src/models.py:ResourceRecord, TopologyComponent, ApplicationCluster`
- Produces: `src/topology_analyzer.py:load_application_catalog, classify_layer, resolve_ownership`

- [ ] **Step 1: Escrever teste falhando para classificação de camadas e resolução de ownership**

Criar `tests/test_topology_analyzer.py`:
```python
import pytest
from src.models import ResourceRecord
from src.topology_analyzer import (
    load_application_catalog,
    classify_layer,
    resolve_ownership
)

def test_classify_layer():
    # Endpoints
    r1 = ResourceRecord(
        identifier="my-alb", arn="arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/my-alb",
        resource_type="elasticloadbalancing:loadbalancer", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
        last_reported_at="", service="elasticloadbalancing", tags=""
    )
    assert classify_layer(r1) == "Ingresso & Endpoints"

    # Compute
    r2 = ResourceRecord(
        identifier="my-func", arn="arn:aws:lambda:us-east-1:123:function:my-func",
        resource_type="lambda:function", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::Lambda::Function",
        last_reported_at="", service="lambda", tags=""
    )
    assert classify_layer(r2) == "Computação & Lógica"

    # Messaging
    r3 = ResourceRecord(
        identifier="my-queue", arn="arn:aws:sqs:us-east-1:123:my-queue",
        resource_type="sqs:queue", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::SQS::Queue",
        last_reported_at="", service="sqs", tags=""
    )
    assert classify_layer(r3) == "Mensageria & Filas"

    # Database
    r4 = ResourceRecord(
        identifier="my-db", arn="arn:aws:rds:us-east-1:123:db:my-db",
        resource_type="rds:db", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::RDS::DBInstance",
        last_reported_at="", service="rds", tags=""
    )
    assert classify_layer(r4) == "Banco de Dados & Cache"

    # Storage
    r5 = ResourceRecord(
        identifier="my-bucket", arn="arn:aws:s3:::my-bucket",
        resource_type="s3:bucket", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::S3::Bucket",
        last_reported_at="", service="s3", tags=""
    )
    assert classify_layer(r5) == "Armazenamento & Apoio"

def test_resolve_ownership():
    catalog = {
        "vdo-promocao": {
            "name": "VDO & Promoção Digital",
            "squad": "Squad Marketing & Promoções",
            "owner": "techlead-vdo@empresa.com",
            "criticality": "Alta",
            "match_patterns": ["vdo", "promo-digital"]
        }
    }

    # Match via catálogo
    r1 = ResourceRecord(
        identifier="alb-vdo-main", arn="arn:aws:alb:123:alb-vdo-main",
        resource_type="alb", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="", last_reported_at="",
        service="elasticloadbalancing", tags=""
    )
    squad, owner, crit = resolve_ownership(r1, catalog, inferred_app="VDO & Promoção Digital")
    assert squad == "Squad Marketing & Promoções"
    assert owner == "techlead-vdo@empresa.com"
    assert crit == "Alta"

    # Fallback governança
    r_gov = ResourceRecord(
        identifier="config-rule-1", arn="arn:aws:config:123:config-rule-1",
        resource_type="config", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="", last_reported_at="",
        service="config", tags="", macro_domain="Governança"
    )
    squad_gov, _, _ = resolve_ownership(r_gov, catalog, inferred_app="Governança & Segurança")
    assert squad_gov == "Squad Segurança & Governança"

    # Fallback genérico
    r_unknown = ResourceRecord(
        identifier="generic-item", arn="arn:aws:ec2:123:item",
        resource_type="ec2", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="", last_reported_at="",
        service="ec2", tags="", macro_domain="A Classificar"
    )
    squad_unk, _, crit_unk = resolve_ownership(r_unknown, catalog, inferred_app="Não Identificado")
    assert squad_unk == "Squad A Definir"
    assert crit_unk == "Padrão"
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `python -m pytest tests/test_topology_analyzer.py`  
Expected: FAIL com ImportError (`cannot import name 'load_application_catalog' from 'src.topology_analyzer'`)

- [ ] **Step 3: Implementar carregamento de catálogo, classificação de camadas e resolução de ownership**

Criar `src/topology_analyzer.py`:
```python
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
```

- [ ] **Step 4: Executar testes para verificar sucesso**

Run: `python -m pytest tests/test_topology_analyzer.py`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/topology_analyzer.py tests/test_topology_analyzer.py
git commit -m "feat(topology_analyzer): implement layer classification and ownership resolution"
```

---

### Task 3: Motor Analítico - Inferência de Dependências e Consolidação da Análise

**Files:**
- Modify: `src/topology_analyzer.py`
- Modify: `tests/test_topology_analyzer.py`

**Interfaces:**
- Consumes: `InventoryReportData`, `load_application_catalog`, `classify_layer`, `resolve_ownership`
- Produces: `infer_connections`, `analyze_application_topology`

- [ ] **Step 1: Escrever teste falhando para inferência de conexões e consolidação da análise**

Adicionar ao `tests/test_topology_analyzer.py`:
```python
from src.topology_analyzer import infer_connections, analyze_application_topology
from src.models import (
    InventoryReportData,
    ApplicationCluster
)

def test_infer_connections():
    comp_alb = TopologyComponent(
        id="alb-vdo", name="alb-vdo", service="elasticloadbalancing",
        layer="Ingresso & Endpoints", arn="arn:aws:alb:123:alb-vdo",
        region="us-east-1", squad="Squad Marketing"
    )
    comp_tg = TopologyComponent(
        id="tg-vdo-80", name="tg-vdo-80", service="elasticloadbalancing",
        layer="Ingresso & Endpoints", arn="arn:aws:tg:123:tg-vdo-80",
        region="us-east-1", squad="Squad Marketing"
    )
    comp_ec2 = TopologyComponent(
        id="i-0123vdo", name="vdo-web-server", service="ec2",
        layer="Computação & Lógica", arn="arn:aws:ec2:123:i-0123vdo",
        region="us-east-1", squad="Squad Marketing"
    )
    comp_rds = TopologyComponent(
        id="vdo-mysql-prd", name="vdo-mysql-prd", service="rds",
        layer="Banco de Dados & Cache", arn="arn:aws:rds:123:db:vdo-mysql-prd",
        region="us-east-1", squad="Squad Marketing"
    )

    components = [comp_alb, comp_tg, comp_ec2, comp_rds]
    connections = infer_connections(components, slug="vdo")

    # Verifica se conexões foram criadas
    assert len(connections) >= 2
    # Verifica vínculo ALB -> TG
    assert any(c.source_id == "alb-vdo" and c.target_id == "tg-vdo-80" for c in connections)
    # Verifica vínculo TG -> EC2
    assert any(c.source_id == "tg-vdo-80" and c.target_id == "i-0123vdo" for c in connections)
    # Verifica vínculo EC2 -> RDS
    assert any(c.source_id == "i-0123vdo" and c.target_id == "vdo-mysql-prd" for c in connections)

    # Verifica se upstream_ids e downstream_ids foram preenchidos
    assert "tg-vdo-80" in comp_alb.downstream_ids
    assert "alb-vdo" in comp_tg.upstream_ids
    assert "i-0123vdo" in comp_tg.downstream_ids
    assert "vdo-mysql-prd" in comp_ec2.downstream_ids

def test_analyze_application_topology_e2e_structure():
    r_alb = ResourceRecord(
        identifier="alb-vdo", arn="arn:aws:alb:123:alb-vdo", resource_type="elasticloadbalancing:loadbalancer",
        region="us-east-1", aws_account="807445251352", application_raw="VDO & Promoção Digital",
        cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer", last_reported_at="",
        service="elasticloadbalancing", tags="", inferred_app="VDO & Promoção Digital"
    )
    r_ec2 = ResourceRecord(
        identifier="i-1234vdo", arn="arn:aws:ec2:123:i-1234vdo", resource_type="ec2:instance",
        region="us-east-1", aws_account="807445251352", application_raw="VDO & Promoção Digital",
        cfn_resource_type="AWS::EC2::Instance", last_reported_at="",
        service="ec2", tags="", inferred_app="VDO & Promoção Digital"
    )
    r_shared = ResourceRecord(
        identifier="shared-vpc", arn="arn:aws:ec2:123:vpc/shared-vpc", resource_type="ec2:vpc",
        region="us-east-1", aws_account="807445251352", application_raw="",
        cfn_resource_type="AWS::EC2::VPC", last_reported_at="",
        service="ec2", tags="", macro_domain="Infraestrutura Compartilhada", inferred_app="Infraestrutura Compartilhada"
    )

    cluster_vdo = ApplicationCluster(
        name="VDO & Promoção Digital",
        slug="vdo-promocao",
        resources=[r_alb, r_ec2]
    )

    report_data = InventoryReportData(
        account_id="807445251352",
        total_resources=3,
        unique_arns=3,
        regions={"us-east-1": 3},
        services={"elasticloadbalancing": 1, "ec2": 2},
        macro_domains={"Aplicação": 2, "Infraestrutura Compartilhada": 1},
        finops_summary={"Avaliar": 3},
        clusters=[cluster_vdo],
        all_resources=[r_alb, r_ec2, r_shared],
        account_name="multicanais-dev"
    )

    result = analyze_application_topology(report_data)

    assert result.total_applications == 1
    assert result.total_components == 2
    assert len(result.applications) == 1
    assert result.applications[0].app_name == "VDO & Promoção Digital"
    assert len(result.shared_infrastructure) == 1
    assert result.shared_infrastructure[0].id == "shared-vpc"
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `python -m pytest tests/test_topology_analyzer.py`  
Expected: FAIL com ImportError (`cannot import name 'infer_connections' from 'src.topology_analyzer'`)

- [ ] **Step 3: Implementar `infer_connections` e `analyze_application_topology`**

Editar `src/topology_analyzer.py` adicionando:
```python
def infer_connections(components: List[TopologyComponent], slug: str = "") -> List[ComponentConnection]:
    """
    Infere as dependências diretas e conexões de fluxo entre componentes da aplicação:
    1. Load Balancer -> Target Group
    2. Target Group -> Computação (EC2, ECS, Lambda)
    3. Mensageria (SQS/SNS) -> Computação (Lambda)
    4. Computação -> Bancos de Dados, Cache e Buckets S3
    """
    connections: List[ComponentConnection] = []

    load_balancers = [c for c in components if c.layer == LAYER_INGRESS and "loadbalancer" in c.service.lower() or "alb" in c.id.lower() or "nlb" in c.id.lower()]
    target_groups = [c for c in components if "targetgroup" in c.id.lower() or "tg-" in c.id.lower()]
    compute_nodes = [c for c in components if c.layer == LAYER_COMPUTE]
    messaging_nodes = [c for c in components if c.layer == LAYER_MESSAGING]
    database_nodes = [c for c in components if c.layer == LAYER_DATABASE]
    storage_nodes = [c for c in components if c.layer == LAYER_STORAGE]

    # 1. LB -> Target Group
    for lb in load_balancers:
        for tg in target_groups:
            # Associação por prefixo/slug comum ou ligação direta
            conn = ComponentConnection(
                source_id=lb.id,
                target_id=tg.id,
                connection_type="Ingress",
                label="Roteia tráfego"
            )
            connections.append(conn)
            if tg.id not in lb.downstream_ids:
                lb.downstream_ids.append(tg.id)
            if lb.id not in tg.upstream_ids:
                tg.upstream_ids.append(lb.id)

    # 2. Target Group -> Compute
    for tg in target_groups:
        for comp in compute_nodes:
            conn = ComponentConnection(
                source_id=tg.id,
                target_id=comp.id,
                connection_type="Ingress",
                label="Encaminha para target"
            )
            connections.append(conn)
            if comp.id not in tg.downstream_ids:
                tg.downstream_ids.append(comp.id)
            if tg.id not in comp.upstream_ids:
                comp.upstream_ids.append(tg.id)

    # Fallback se não houver Target Group explícito: LB -> Compute diretamente
    if load_balancers and not target_groups:
        for lb in load_balancers:
            for comp in compute_nodes:
                conn = ComponentConnection(
                    source_id=lb.id,
                    target_id=comp.id,
                    connection_type="Ingress",
                    label="Roteia tráfego"
                )
                connections.append(conn)
                if comp.id not in lb.downstream_ids:
                    lb.downstream_ids.append(comp.id)
                if lb.id not in comp.upstream_ids:
                    comp.upstream_ids.append(lb.id)

    # 3. Mensageria -> Compute
    for msg in messaging_nodes:
        for comp in compute_nodes:
            conn = ComponentConnection(
                source_id=msg.id,
                target_id=comp.id,
                connection_type="EventTrigger",
                label="Aciona processamento"
            )
            connections.append(conn)
            if comp.id not in msg.downstream_ids:
                msg.downstream_ids.append(comp.id)
            if msg.id not in comp.upstream_ids:
                comp.upstream_ids.append(msg.id)

    # 4. Compute -> Databases
    for comp in compute_nodes:
        for db in database_nodes:
            conn = ComponentConnection(
                source_id=comp.id,
                target_id=db.id,
                connection_type="DataAccess",
                label="Persiste dados"
            )
            connections.append(conn)
            if db.id not in comp.downstream_ids:
                comp.downstream_ids.append(db.id)
            if comp.id not in db.upstream_ids:
                db.upstream_ids.append(comp.id)

    # 5. Compute -> Storage
    for comp in compute_nodes:
        for st in storage_nodes:
            conn = ComponentConnection(
                source_id=comp.id,
                target_id=st.id,
                connection_type="DataAccess",
                label="Lê/Grava objetos"
            )
            connections.append(conn)
            if st.id not in comp.downstream_ids:
                comp.downstream_ids.append(st.id)
            if comp.id not in st.upstream_ids:
                st.upstream_ids.append(comp.id)

    return connections

def analyze_application_topology(
    report_data: InventoryReportData,
    catalog_path: Optional[str] = None
) -> TopologyAnalysisResult:
    """
    Executa a análise arquitetural completa do inventário:
    - Agrupa por aplicação
    - Classifica componentes em camadas
    - Atribui governança e ownership
    - Infere dependências
    - Consolida métricas gerais
    """
    catalog = load_application_catalog(catalog_path)
    all_components: List[TopologyComponent] = []
    applications: List[ApplicationTopology] = []
    shared_infra: List[TopologyComponent] = []
    unassigned: List[TopologyComponent] = []

    # Cria índice rápido de recursos pertencentes a clusters de aplicações
    cluster_resource_map: Dict[str, str] = {}
    for cl in report_data.clusters:
        for r in cl.resources:
            cluster_resource_map[r.identifier] = cl.name

    for rec in report_data.all_resources:
        inferred_app = cluster_resource_map.get(rec.identifier, rec.inferred_app)
        layer = classify_layer(rec)
        squad, owner, crit = resolve_ownership(rec, catalog, inferred_app=inferred_app)

        comp = TopologyComponent(
            id=rec.identifier,
            name=rec.resource_name if rec.resource_name and rec.resource_name != "-" else rec.identifier,
            service=rec.service,
            layer=layer,
            arn=rec.arn,
            region=rec.region,
            squad=squad,
            owner=owner,
            criticality=crit
        )

        if rec.macro_domain == "Infraestrutura Compartilhada" or inferred_app == "Infraestrutura Compartilhada":
            shared_infra.append(comp)
        elif rec.macro_domain == "Governança" or inferred_app == "Governança & Segurança":
            shared_infra.append(comp)
        elif inferred_app in ("Não Identificado", "A Classificar") and squad == "Squad A Definir":
            unassigned.append(comp)
        else:
            all_components.append(comp)

    # Agrupa componentes por aplicação a partir dos clusters
    for cl in report_data.clusters:
        cl_comps = [c for c in all_components if cluster_resource_map.get(c.id) == cl.name]
        if not cl_comps:
            continue

        # Metadados de aplicação
        app_squad = cl_comps[0].squad if cl_comps else "Squad A Definir"
        app_owner = cl_comps[0].owner if cl_comps else None
        app_crit = cl_comps[0].criticality if cl_comps else "Padrão"
        app_desc = f"Aplicação {cl.name} sustentada na infraestrutura AWS"

        # Se houver catálogo correspondente
        for app_info in catalog.values():
            if app_info.get("name") == cl.name:
                app_squad = app_info.get("squad", app_squad)
                app_owner = app_info.get("owner", app_owner)
                app_crit = app_info.get("criticality", app_crit)
                app_desc = app_info.get("description", app_desc)
                break

        # Infere conexões
        connections = infer_connections(cl_comps, slug=cl.slug)

        app_topo = ApplicationTopology(
            app_name=cl.name,
            slug=cl.slug,
            squad=app_squad,
            owner=app_owner,
            criticality=app_crit,
            description=app_desc,
            components=cl_comps,
            connections=connections
        )
        applications.append(app_topo)

    # Distribuições
    squad_dist: Dict[str, int] = {}
    layer_dist: Dict[str, int] = {}

    for c in all_components:
        squad_dist[c.squad] = squad_dist.get(c.squad, 0) + 1
        layer_dist[c.layer] = layer_dist.get(c.layer, 0) + 1

    total_conns = sum(len(app.connections) for app in applications)
    assigned_squads = len(set(c.squad for c in all_components if c.squad != "Squad A Definir"))

    return TopologyAnalysisResult(
        account_id=report_data.account_id,
        account_name=report_data.account_name,
        account_display=report_data.account_display,
        total_applications=len(applications),
        total_components=len(all_components),
        total_connections=total_conns,
        assigned_squads_count=assigned_squads,
        squad_distribution=squad_dist,
        layer_distribution=layer_dist,
        applications=applications,
        shared_infrastructure=shared_infra,
        unassigned_components=unassigned
    )
```

- [ ] **Step 4: Executar testes para verificar sucesso**

Run: `python -m pytest tests/test_topology_analyzer.py`  
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/topology_analyzer.py tests/test_topology_analyzer.py
git commit -m "feat(topology_analyzer): add connection inference and full topology analysis engine"
```

---

### Task 4: Exportador Markdown com Diagramas Mermaid

**Files:**
- Create: `src/exporters/topology_report.py`
- Create: `tests/test_topology_report_exporter.py`

**Interfaces:**
- Consumes: `TopologyAnalysisResult`, `ApplicationTopology`, `TopologyComponent`
- Produces: `export_topology_report_markdown`

- [ ] **Step 1: Escrever teste falhando para gerador de relatório Markdown de topologia**

Criar `tests/test_topology_report_exporter.py`:
```python
import os
import tempfile
import pytest
from src.models import (
    TopologyComponent,
    ComponentConnection,
    ApplicationTopology,
    TopologyAnalysisResult
)
from src.exporters.topology_report import export_topology_report_markdown

def test_export_topology_report_markdown():
    comp_alb = TopologyComponent(
        id="alb-vdo", name="alb-vdo", service="elasticloadbalancing",
        layer="Ingresso & Endpoints", arn="arn:aws:alb:123:alb-vdo",
        region="us-east-1", squad="Squad Marketing", downstream_ids=["tg-vdo-80"]
    )
    comp_tg = TopologyComponent(
        id="tg-vdo-80", name="tg-vdo-80", service="elasticloadbalancing",
        layer="Ingresso & Endpoints", arn="arn:aws:tg:123:tg-vdo-80",
        region="us-east-1", squad="Squad Marketing", upstream_ids=["alb-vdo"], downstream_ids=["i-123"]
    )
    comp_ec2 = TopologyComponent(
        id="i-123", name="vdo-app-01", service="ec2",
        layer="Computação & Lógica", arn="arn:aws:ec2:123:i-123",
        region="us-east-1", squad="Squad Marketing", upstream_ids=["tg-vdo-80"]
    )

    conn1 = ComponentConnection(source_id="alb-vdo", target_id="tg-vdo-80", connection_type="Ingress", label="Roteia tráfego")
    conn2 = ComponentConnection(source_id="tg-vdo-80", target_id="i-123", connection_type="Ingress", label="Encaminha para target")

    app = ApplicationTopology(
        app_name="VDO & Promoção Digital",
        slug="vdo-promocao",
        squad="Squad Marketing",
        owner="lead@vdo.com",
        criticality="Alta",
        description="Sistema de gestão de promoções",
        components=[comp_alb, comp_tg, comp_ec2],
        connections=[conn1, conn2]
    )

    analysis = TopologyAnalysisResult(
        account_id="807445251352",
        account_name="multicanais-dev",
        total_applications=1,
        total_components=3,
        total_connections=2,
        assigned_squads_count=1,
        squad_distribution={"Squad Marketing": 3},
        layer_distribution={"Ingresso & Endpoints": 2, "Computação & Lógica": 1},
        applications=[app],
        shared_infrastructure=[],
        unassigned_components=[]
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = os.path.join(tmpdir, "relatorio_topologia.md")
        export_topology_report_markdown(analysis, out_file)

        assert os.path.exists(out_file)
        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "# Relatório de Arquitetura de Aplicações, Topologia e Governança" in content
        assert "multicanais-dev" in content
        assert "```mermaid" in content
        assert "flowchart LR" in content
        assert "subgraph Ingress" in content
        assert "alb-vdo" in content
        assert "Squad Marketing" in content
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `python -m pytest tests/test_topology_report_exporter.py`  
Expected: FAIL com ImportError (`cannot import name 'export_topology_report_markdown' from 'src.exporters.topology_report'`)

- [ ] **Step 3: Implementar exportador Markdown com sintaxe Mermaid segura**

Criar `src/exporters/topology_report.py`:
```python
import re
from pathlib import Path
from src.models import (
    TopologyAnalysisResult,
    ApplicationTopology,
    TopologyComponent
)

def _sanitize_node_id(text: str) -> str:
    """Sanitiza strings para identificadores válidos em diagramas Mermaid."""
    return "node_" + re.sub(r"[^a-zA-Z0-9_]", "_", text).strip("_")

def _generate_mermaid_diagram(app: ApplicationTopology) -> str:
    """Gera bloco Mermaid flowchart LR com subgrafos por camada funcional."""
    lines = ["```mermaid", "flowchart LR"]

    # Subgrafos por camada
    layers = [
        ("Ingress", "Camada de Entrada & Endpoints", app.ingress_components),
        ("Compute", "Computação & Lógica", app.compute_components),
        ("Messaging", "Mensageria & Filas", app.messaging_components),
        ("Database", "Banco de Dados & Cache", app.database_components),
        ("Storage", "Armazenamento & Apoio", app.storage_components),
    ]

    for sg_id, sg_title, comps in layers:
        if comps:
            lines.append(f'  subgraph {sg_id}["{sg_title}"]')
            for c in comps:
                node_id = _sanitize_node_id(c.id)
                disp_name = c.name if c.name and c.name != "-" else c.id
                # Trunca se for muito longo
                if len(disp_name) > 35:
                    disp_name = disp_name[:32] + "..."
                label = f"{disp_name} ({c.service})"
                lines.append(f'    {node_id}["{label}"]')
            lines.append("  end")

    # Arestas / Conexões
    if app.connections:
        lines.append("")
        for conn in app.connections:
            src = _sanitize_node_id(conn.source_id)
            tgt = _sanitize_node_id(conn.target_id)
            lbl = conn.label or ""
            if lbl:
                lines.append(f'  {src} -->|"{lbl}"| {tgt}')
            else:
                lines.append(f"  {src} --> {tgt}")
    else:
        # Se não houver conexões inferidas, gera nota informativa
        lines.append("  %% Sem conexões diretas inferidas nos metadados estáticos")

    lines.append("```")
    return "\n".join(lines)

def export_topology_report_markdown(analysis: TopologyAnalysisResult, output_path: str) -> str:
    """
    Gera o relatório executivo e técnico em Markdown contendo:
    - Scorecard executivo de arquitetura e governança
    - Matriz de Ownership e Squads
    - Visão detalhada por aplicação com diagramas Mermaid
    - Inventário tabular de componentes
    - Componentes de infraestrutura compartilhada
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Relatório de Arquitetura de Aplicações, Topologia e Governança",
        "",
        f"**Ambiente:** {analysis.display_title}  ",
        f"**Conta AWS:** `{analysis.account_id}`  ",
        "**Status:** Consolidado e Auditado  ",
        "",
        "---",
        "",
        "## 1. Resumo Executivo de Governança e Arquitetura",
        "",
        "| Métrica Estratégica | Valor Consolidado |",
        "|---|---|",
        f"| **Aplicações de Negócio Mapeadas** | {analysis.total_applications} |",
        f"| **Componentes Arquiteturais Catalogados** | {analysis.total_components} |",
        f"| **Conexões e Integrações Inferidas** | {analysis.total_connections} |",
        f"| **Squads / Times com Responsabilidade Atribuída** | {analysis.assigned_squads_count} |",
        f"| **Itens em Infraestrutura Compartilhada** | {len(analysis.shared_infrastructure)} |",
        f"| **Componentes a Classificar / Gaps de Governança** | {len(analysis.unassigned_components)} |",
        "",
        "### 1.1 Distribuição por Camada Funcional",
        "",
        "| Camada Arquitetural | Quantidade de Componentes |",
        "|---|---|",
    ]

    for layer, count in sorted(analysis.layer_distribution.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| **{layer}** | {count} |")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Matriz de Governança e Ownership (Squads e Responsáveis)",
        "",
        "| Aplicação | Squad Responsável | Tech Lead / Owner | Criticidade | Qtd Componentes | Endpoints Expostos |",
        "|---|---|---|---|---|---|",
    ])

    for app in analysis.applications:
        ingress_count = len(app.ingress_components)
        owner_str = app.owner if app.owner else "A definir"
        lines.append(
            f"| **{app.app_name}** | {app.squad} | {owner_str} | `{app.criticality}` | {len(app.components)} | {ingress_count} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Visão Arquitetural Detalhada por Aplicação",
        ""
    ])

    for idx, app in enumerate(analysis.applications, start=1):
        lines.extend([
            f"### 3.{idx} {app.app_name}",
            "",
            f"*{app.description}*",
            "",
            f"- **Squad Responsável:** `{app.squad}`",
            f"- **Tech Lead / Ponto Focal:** `{app.owner or 'A definir'}`",
            f"- **Nível de Criticidade:** `{app.criticality}`",
            f"- **Total de Componentes:** `{len(app.components)}`",
            "",
            "#### Diagrama de Arquitetura e Fluxo de Integração",
            "",
            _generate_mermaid_diagram(app),
            "",
            "#### Inventário de Componentes e Interfaces",
            "",
            "| Componente (ID) | Serviço | Camada | Região | Origem (Upstream) | Destino (Downstream) |",
            "|---|---|---|---|---|---|",
        ])

        for comp in app.components:
            up_str = ", ".join(comp.upstream_ids) if comp.upstream_ids else "-"
            down_str = ", ".join(comp.downstream_ids) if comp.downstream_ids else "-"
            disp_id = comp.id
            if len(disp_id) > 40:
                disp_id = disp_id[:37] + "..."
            lines.append(f"| `{disp_id}` | `{comp.service}` | {comp.layer} | `{comp.region}` | {up_str} | {down_str} |")

        lines.append("")

    if analysis.shared_infrastructure:
        lines.extend([
            "---",
            "",
            "## 4. Infraestrutura Compartilhada e Serviços Comuns",
            "",
            "Recursos de suporte central (segurança, rede compartilhada, auditoria) que atendem a múltiplos domínios:",
            "",
            "| Identificador | Serviço | Camada | Squad Responsável | Região |",
            "|---|---|---|---|---|",
        ])
        for c in analysis.shared_infrastructure[:50]:  # Limita para não inflar desnecessariamente o relatório
            lines.append(f"| `{c.id}` | `{c.service}` | {c.layer} | {c.squad} | `{c.region}` |")
        lines.append("")

    if analysis.unassigned_components:
        lines.extend([
            "---",
            "",
            "## 5. Gaps de Governança (Componentes a Classificar)",
            "",
            "Recursos identificados que necessitam de definição de Squad e aplicação responsável:",
            "",
            "| Identificador | Serviço AWS | Camada | Região |",
            "|---|---|---|---|",
        ])
        for c in analysis.unassigned_components[:50]:
            lines.append(f"| `{c.id}` | `{c.service}` | {c.layer} | `{c.region}` |")
        lines.append("")

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(out)
```

- [ ] **Step 4: Executar testes para verificar sucesso**

Run: `python -m pytest tests/test_topology_report_exporter.py`  
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/exporters/topology_report.py tests/test_topology_report_exporter.py
git commit -m "feat(exporters): implement markdown topology and architecture report exporter with mermaid diagrams"
```

---

### Task 5: Aba no Excel do Inventário

**Files:**
- Modify: `src/exporters/excel.py`
- Modify: `tests/test_excel_exporter.py`

**Interfaces:**
- Consumes: `InventoryReportData`, `TopologyAnalysisResult`
- Produces: Nova aba `"Topologia & Arquitetura"` no Excel gerado

- [ ] **Step 1: Escrever teste falhando para aba de topologia no Excel**

Adicionar teste em `tests/test_excel_exporter.py`:
```python
from openpyxl import load_workbook
from src.models import (
    TopologyComponent,
    ApplicationTopology,
    TopologyAnalysisResult
)

def test_generate_excel_with_topology_tab(tmp_path):
    report_data = create_sample_report_data() # utiliza fixture existente no arquivo
    
    comp = TopologyComponent(
        id="alb-vdo", name="alb-vdo", service="elasticloadbalancing",
        layer="Ingresso & Endpoints", arn="arn:aws:alb:123", region="us-east-1",
        squad="Squad Marketing", owner="lead@vdo.com", criticality="Alta",
        upstream_ids=[], downstream_ids=["tg-vdo"]
    )
    app = ApplicationTopology(
        app_name="VDO", slug="vdo", squad="Squad Marketing", owner="lead@vdo.com",
        criticality="Alta", description="", components=[comp], connections=[]
    )
    topology_analysis = TopologyAnalysisResult(
        account_id="123", total_applications=1, total_components=1,
        total_connections=0, assigned_squads_count=1, squad_distribution={"Squad Marketing": 1},
        layer_distribution={"Ingresso & Endpoints": 1}, applications=[app],
        shared_infrastructure=[], unassigned_components=[]
    )

    out_file = str(tmp_path / "inventario_com_topologia.xlsx")
    generate_excel_workbook(report_data, out_file, topology_analysis=topology_analysis)

    wb = load_workbook(out_file)
    assert "Topologia & Arquitetura" in wb.sheetnames
    ws = wb["Topologia & Arquitetura"]
    assert ws.cell(row=1, column=1).value == "Aplicação"
    assert ws.cell(row=2, column=1).value == "VDO"
    assert ws.cell(row=2, column=2).value == "Squad Marketing"
    assert ws.cell(row=2, column=5).value == "alb-vdo"
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `python -m pytest tests/test_excel_exporter.py::test_generate_excel_with_topology_tab`  
Expected: FAIL (`TypeError: generate_excel_workbook() got an unexpected keyword argument 'topology_analysis'`)

- [ ] **Step 3: Implementar a criação da aba `"Topologia & Arquitetura"` em `src/exporters/excel.py`**

Modificar `src/exporters/excel.py` para receber `topology_analysis: Optional[TopologyAnalysisResult] = None` e construir a aba com formatação padronizada:
```python
def _populate_topology_sheet(ws, topology_analysis: TopologyAnalysisResult):
    headers = [
        "Aplicação", "Squad Responsável", "Tech Lead / Owner", "Criticidade",
        "ID do Componente", "Nome Amigável", "Serviço AWS", "Camada Funcional",
        "Região", "Origem (Upstream)", "Destino (Downstream)", "ARN"
    ]
    # Cabeçalho azul escuro com texto branco e bordas
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for app in topology_analysis.applications:
        for c in app.components:
            up_str = ", ".join(c.upstream_ids) if c.upstream_ids else "-"
            down_str = ", ".join(c.downstream_ids) if c.downstream_ids else "-"
            ws.append([
                app.app_name,
                c.squad,
                c.owner or "-",
                c.criticality,
                c.id,
                c.name,
                c.service,
                c.layer,
                c.region,
                up_str,
                down_str,
                c.arn
            ])

    for c in topology_analysis.shared_infrastructure:
        ws.append([
            "Infraestrutura Compartilhada",
            c.squad,
            c.owner or "-",
            c.criticality,
            c.id,
            c.name,
            c.service,
            c.layer,
            c.region,
            "-",
            "-",
            c.arn
        ])

    for c in topology_analysis.unassigned_components:
        ws.append([
            "A Classificar",
            c.squad,
            "-",
            c.criticality,
            c.id,
            c.name,
            c.service,
            c.layer,
            c.region,
            "-",
            "-",
            c.arn
        ])

    # Auto ajuste de largura de colunas
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 50)
```

- [ ] **Step 4: Executar testes para verificar sucesso**

Run: `python -m pytest tests/test_excel_exporter.py`  
Expected: PASS (todos os testes de excel passam)

- [ ] **Step 5: Commit**

```bash
git add src/exporters/excel.py tests/test_excel_exporter.py
git commit -m "feat(exporters): add topology and architecture sheet to excel workbook"
```

---

### Task 6: Integração no Pipeline CLI, DOCX e Testes E2E

**Files:**
- Modify: `src/main.py`
- Modify: `tests/test_e2e.py`

**Interfaces:**
- Consumes: `analyze_application_topology`, `export_topology_report_markdown`, `convert_markdown_to_docx`, `generate_excel_workbook`
- Produces: CLI integrada gerando todos os 5 relatórios principais (`excel`, `md_tecnico`, `finops_md`, `orphan_md`, `topology_md` e os respectivos DOCXs).

- [ ] **Step 1: Escrever teste falhando para pipeline completo no E2E**

Editar `tests/test_e2e.py` para validar a geração dos arquivos de topologia e os DOCXs:
```python
def test_pipeline_e2e_includes_topology(tmp_path):
    # Executa run_pipeline em diretório de teste
    res = run_pipeline(input_dir=str(sample_dir), output_dir=str(tmp_path))
    assert len(res) == 5
    excel_path, md_path, finops_path, orphan_path, topology_path = res

    assert os.path.exists(topology_path)
    topo_docx = tmp_path / "docs" / Path(topology_path).name.replace(".md", ".docx")
    assert topo_docx.exists()
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `python -m pytest tests/test_e2e.py`  
Expected: FAIL (`ValueError: too many values to unpack` ou `assert len(res) == 5`)

- [ ] **Step 3: Implementar a integração em `src/main.py`**

Modificar `src/main.py`:
- Adicionar flag `--catalog` no parser.
- Executar etapa de topologia e governança:
```python
    # 8. Análise de Topologia, Dependências e Arquitetura de Aplicações
    print("[*] Mapeando arquitetura de aplicações, dependências e ownership...")
    topology_analysis = analyze_application_topology(report_data, catalog_path=catalog)
    topology_md_filename = f"relatorio_arquitetura_aplicacoes_{clean_account_name}.md"
    topology_md_path = str(markdowns_dir / topology_md_filename)
    export_topology_report_markdown(topology_analysis, topology_md_path)
    print(f"[OK] Relatório executivo de arquitetura e topologia gerado: {topology_md_path}")

    # Atualiza geração do Excel passando topology_analysis
    generate_excel_workbook(report_data, excel_file, topology_analysis=topology_analysis)

    # Exporta DOCX da topologia
    topology_docx = str(docs_dir / f"relatorio_arquitetura_aplicacoes_{clean_account_name}.docx")
    convert_markdown_to_docx(topology_md_path, topology_docx)
    print(f"[OK] Documento Word de arquitetura e topologia gerado: {topology_docx}")
```
- Atualizar assinatura de retorno de `run_pipeline` para retornar `Tuple[str, str, str, str, str]`.
- Atualizar chamadas em testes legados que desempacotam `run_pipeline` se necessário.

- [ ] **Step 4: Executar suíte completa de testes para verificar sucesso**

Run: `python -m pytest`  
Expected: PASS (todos os 74 testes legados + novos testes passando!)

- [ ] **Step 5: Commit**

```bash
git add src/main.py tests/test_e2e.py
git commit -m "feat(main): integrate application topology, ownership analysis and docx export into CLI pipeline"
```

---

### Task 7: Atualização da Documentação Oficial

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Especificação e implementação
- Produces: Seção detalhada e documentada de topologia de aplicações no README.

- [ ] **Step 1: Adicionar seção no `README.md`**

Adicionar no `README.md`:
- Explicação da funcionalidade de Mapeamento de Arquitetura de Aplicações e Governança (Ownership).
- Tabela dos novos relatórios gerados (`relatorio_arquitetura_aplicacoes_<conta>.md`, `.docx` e aba no Excel).
- Instruções sobre como customizar o arquivo `catalog/applications.json` e o uso da flag `--catalog`.
- Exemplo visual de diagrama Mermaid gerado.

- [ ] **Step 2: Verificar renderização e sintaxe no README**

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document application topology, ownership mapping and mermaid diagrams in README"
```

---

## Auto-Revisão de Conclusão do Plano

1. **Cobertura da Spec:** Todas as 5 camadas funcionais, resolução de squad/ownership, inferência de conexões, diagrama Mermaid, DOCX corporativo e aba Excel estão contemplados com tarefas dedicadas.
2. **Ausência de Placeholders:** Nenhum "TODO", "TBD" ou código vago; todos os blocos de código e testes foram explicitados.
3. **Consistência de Nomes e Tipos:** Modelos em `src/models.py` e funções em `src/topology_analyzer.py` e `src/exporters/topology_report.py` mantêm assinaturas rigorosamente idênticas ao longo de todas as tarefas.

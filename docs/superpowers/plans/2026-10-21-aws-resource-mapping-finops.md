# AWS Resource Mapping and FinOps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable, modular Python tool to ingest, deduplicate, and correlate AWS resource inventory CSVs, map computing workloads and application clusters, and generate FinOps advisory Excel workbooks and Markdown reports.

**Architecture:** A 4-stage pipeline (Ingestion & Canonical Deduplication ➔ Application & Topology Correlator ➔ FinOps Advisory Rules Engine ➔ Multi-format Exporters for Excel and Markdown) coordinated via a clean CLI interface.

**Tech Stack:** Python 3.10+, openpyxl, pytest, standard libraries (dataclasses, argparse, csv, pathlib, re).

**Spec:** `docs/superpowers/specs/2026-10-21-aws-resource-mapping-finops-design.md`

## Global Constraints
- Must operate completely offline using local CSV exports without requiring live AWS credentials or network access.
- Canonical primary key is the resource `ARN` (with fallback to `service:resource_type:region:identifier`).
- Must handle character encodings gracefully (`utf-8`, `utf-8-sig`, `iso-8859-1`, `cp1252`).
- All FinOps recommendations must be advisory suggestions with standardized categories and justifications, providing dedicated blank columns for human team review (`Decisão do Time`, `Responsável`, `Observações`).
- All tests must be executed with `python -m pytest`.

---

### Task 1: Core Domain Models (`src/models.py`)

**Files:**
- Create: `src/__init__.py`
- Create: `src/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `ResourceRecord(identifier: str, arn: str, resource_type: str, region: str, aws_account: str, application_raw: str, cfn_resource_type: str, last_reported_at: str, service: str, tags: str, source_files: list[str], macro_domain: str = "A Classificar", inferred_app: str = "Não Identificado", finops_suggestion: str = "Avaliar", finops_cost_impact: str = "Baixo/Zero", finops_rationale: str = "")`
  - `ApplicationCluster(name: str, slug: str, resources: list[ResourceRecord], compute_instances: list[str], load_balancers: list[str], target_groups: list[str], databases: list[str], secrets: list[str], storage_buckets: list[str])`
  - `InventoryReportData(account_id: str, total_resources: int, unique_arns: int, regions: dict[str, int], services: dict[str, int], macro_domains: dict[str, int], finops_summary: dict[str, int], clusters: list[ApplicationCluster], all_resources: list[ResourceRecord])`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
import pytest
from src.models import ResourceRecord, ApplicationCluster, InventoryReportData

def test_resource_record_defaults():
    record = ResourceRecord(
        identifier="i-123456",
        arn="arn:aws:ec2:ca-central-1:123456789012:instance/i-123456",
        resource_type="ec2:instance",
        region="ca-central-1",
        aws_account="123456789012",
        application_raw="-",
        cfn_resource_type="AWS::EC2::Instance",
        last_reported_at="2026-10-21 10:00:00",
        service="ec2",
        tags="0",
        source_files=["ec2.csv"]
    )
    assert record.identifier == "i-123456"
    assert record.macro_domain == "A Classificar"
    assert record.inferred_app == "Não Identificado"
    assert record.finops_suggestion == "Avaliar"
    assert record.source_files == ["ec2.csv"]

def test_application_cluster_initialization():
    cluster = ApplicationCluster(
        name="Canais Digitais",
        slug="canais-dig",
        resources=[],
        compute_instances=["i-123"],
        load_balancers=["app/alb-1"],
        target_groups=["tg-1"],
        databases=["canaisdb-02"],
        secrets=["canais-db-01"],
        storage_buckets=["logs-canaisdig"]
    )
    assert cluster.name == "Canais Digitais"
    assert len(cluster.compute_instances) == 1
    assert cluster.databases == ["canaisdb-02"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/__init__.py
"""AWS Resource Mapping & FinOps Pipeline."""

# src/models.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/__init__.py src/models.py tests/test_models.py
git commit -m "feat(models): define ResourceRecord, ApplicationCluster and InventoryReportData"
```

---

### Task 2: CSV Ingestion & Canonical Deduplication (`src/ingestion.py`)

**Files:**
- Create: `src/ingestion.py`
- Test: `tests/test_ingestion.py`

**Interfaces:**
- Consumes: `ResourceRecord` from `src.models`
- Produces: `load_and_deduplicate_csvs(directory_path: str) -> list[ResourceRecord]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingestion.py
import pytest
from pathlib import Path
from src.ingestion import load_and_deduplicate_csvs

def test_load_and_deduplicate_merges_files(tmp_path: Path):
    file1 = tmp_path / "resources.csv"
    file2 = tmp_path / "ec2.csv"
    
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row1 = "i-111,arn:aws:ec2:ca-central-1:807445251352:instance/i-111,ec2:instance,ca-central-1,807445251352,-,AWS::EC2::Instance,2026-10-10 10:00:00,ec2,0\n"
    row2 = "i-222,arn:aws:ec2:ca-central-1:807445251352:instance/i-222,ec2:instance,ca-central-1,807445251352,-,AWS::EC2::Instance,2026-10-10 10:00:00,ec2,0\n"
    # row1 again in ec2.csv with newer timestamp
    row1_newer = "i-111,arn:aws:ec2:ca-central-1:807445251352:instance/i-111,ec2:instance,ca-central-1,807445251352,-,AWS::EC2::Instance,2026-10-15 12:00:00,ec2,0\n"
    
    file1.write_text(header + row1 + row2, encoding="utf-8")
    file2.write_text(header + row1_newer, encoding="utf-8")
    
    records = load_and_deduplicate_csvs(str(tmp_path))
    
    assert len(records) == 2
    rec1 = next(r for r in records if r.identifier == "i-111")
    assert rec1.last_reported_at == "2026-10-15 12:00:00"
    assert set(rec1.source_files) == {"resources.csv", "ec2.csv"}

def test_load_and_deduplicate_handles_encoding_fallback(tmp_path: Path):
    latin_file = tmp_path / "latin.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row = "regra-1,arn:aws:config:sa-east-1:123:rule/1,config:rule,sa-east-1,123,-,AWS::Config::Rule,2026-10-10,config,0\n"
    latin_file.write_bytes((header + row).encode("iso-8859-1"))
    
    records = load_and_deduplicate_csvs(str(tmp_path))
    assert len(records) == 1
    assert records[0].identifier == "regra-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingestion.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ingestion'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ingestion.py
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
            with open(file_path, "r", encoding=enc) as f:
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
            ident = row.get("Identificador", "").strip()
            arn = row.get("ARN", "").strip()
            res_type = row.get("Tipo de recurso", "").strip()
            region = row.get("Região", "").strip()
            account = row.get("Conta da AWS", "").strip()
            app_raw = row.get("Aplicação", "").strip()
            cfn_type = row.get("CfnResourceType", "").strip()
            last_reported = row.get("LastReportedAt", "").strip()
            service = row.get("Serviço", "").strip()
            tags = row.get("Tags", "0").strip()

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ingestion.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ingestion.py tests/test_ingestion.py
git commit -m "feat(ingestion): implement resilient CSV loader with canonical ARN deduplication"
```

---

### Task 3: Domain & Application Topology Correlator (`src/correlator.py`)

**Files:**
- Create: `src/correlator.py`
- Test: `tests/test_correlator.py`

**Interfaces:**
- Consumes: `list[ResourceRecord]` from `src.models`
- Produces: `correlate_and_classify_resources(resources: list[ResourceRecord]) -> tuple[list[ResourceRecord], list[ApplicationCluster]]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_correlator.py
import pytest
from src.models import ResourceRecord
from src.correlator import correlate_and_classify_resources

def test_governance_classification():
    records = [
        ResourceRecord(
            identifier="StackSet-AWSControlTowerBP-BASELINE-CLOUDWATCH",
            arn="arn:aws:cloudformation:ca-central-1:123:stack/StackSet-AWSControlTowerBP",
            resource_type="cloudformation:stack",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::CloudFormation::Stack",
            last_reported_at="2026-10-10",
            service="cloudformation",
            tags="0"
        ),
        ResourceRecord(
            identifier="aws-service-rule/fms.amazonaws.com/config-rule-ccwwdc",
            arn="arn:aws:config:us-east-1:123:config-rule/aws-service-rule/fms",
            resource_type="config:config-rule",
            region="us-east-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::Config::ConfigRule",
            last_reported_at="2026-10-10",
            service="config",
            tags="0"
        )
    ]
    classified, clusters = correlate_and_classify_resources(records)
    assert all(r.macro_domain == "Governança" for r in classified)

def test_application_clustering_and_topology():
    records = [
        ResourceRecord(
            identifier="app/alb-blog-wordpress/71ffc2bd913c4691",
            arn="arn:aws:elasticloadbalancing:ca-central-1:123:loadbalancer/app/alb-blog-wordpress/71ffc2bd913c4691",
            resource_type="elasticloadbalancing:loadbalancer",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
            last_reported_at="2026-10-10",
            service="elasticloadbalancing",
            tags="0"
        ),
        ResourceRecord(
            identifier="blog-wordpress/8c0f1e8481be211d",
            arn="arn:aws:elasticloadbalancing:ca-central-1:123:targetgroup/blog-wordpress/8c0f1e8481be211d",
            resource_type="elasticloadbalancing:targetgroup",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::ElasticLoadBalancingV2::TargetGroup",
            last_reported_at="2026-10-10",
            service="elasticloadbalancing",
            tags="0"
        ),
        ResourceRecord(
            identifier="canaisdb-02",
            arn="arn:aws:rds:ca-central-1:123:db:canaisdb-02",
            resource_type="rds:db",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::RDS::DBInstance",
            last_reported_at="2026-10-10",
            service="rds",
            tags="0"
        )
    ]
    classified, clusters = correlate_and_classify_resources(records)
    wp_rec = next(r for r in classified if "wordpress" in r.identifier.lower())
    assert wp_rec.inferred_app == "WordPress / Blog"
    assert wp_rec.macro_domain == "Aplicação"
    
    canais_rec = next(r for r in classified if "canais" in r.identifier.lower())
    assert canais_rec.inferred_app == "Canais Digitais"
    
    cluster_names = [c.name for c in clusters]
    assert "WordPress / Blog" in cluster_names
    assert "Canais Digitais" in cluster_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_correlator.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.correlator'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/correlator.py
import re
from typing import List, Tuple, Dict
from src.models import ResourceRecord, ApplicationCluster

GOVERNANCE_PATTERNS = [
    r"StackSet-AWSControlTower",
    r"aws-controltower",
    r"aws-service-rule/fms",
    r"aws-service-rule/securityhub",
    r"StackSet-SH-",
    r"StackSet-PrismaCloud",
    r"crowdstrike",
    r"/CrowdStrike/",
    r"StackSet-VisionOne",
    r"StackSet-AWS-QuickSetup",
    r"aws-quicksetup",
    r"StackSet-CustomControlTow",
    r"StackSet-sra-",
    r"StackSet-PSG-",
    r"^AWS-",
    r"^Amazon",
    r"AWSServiceRole",
    r"config-rule-"
]

KNOWN_APP_SLUGS = [
    ("canais-dig", "Canais Digitais"),
    ("canaisdb", "Canais Digitais"),
    ("multicanais", "Canais Digitais"),
    ("wordpress", "WordPress / Blog"),
    ("blog", "WordPress / Blog"),
    ("docker-dev", "Docker-dev"),
    ("promo-digital", "VDO & Promoção Digital"),
    ("promodb", "VDO & Promoção Digital"),
    ("porto-vdo", "VDO & Promoção Digital"),
    ("alb-vdo", "VDO & Promoção Digital"),
    ("ftp-vdo", "VDO & Promoção Digital"),
    ("elasticbeanstalk", "Elastic Beanstalk / Legado")
]

def _is_governance(record: ResourceRecord) -> bool:
    target_str = f"{record.identifier} {record.arn} {record.service}"
    for pat in GOVERNANCE_PATTERNS:
        if re.search(pat, target_str, re.IGNORECASE):
            return True
    if record.service in ("config", "shield", "servicecatalog") and not any(k[0] in target_str.lower() for k in KNOWN_APP_SLUGS):
        return True
    return False

def _infer_app_name(record: ResourceRecord) -> str:
    target_str = f"{record.identifier} {record.arn}".lower()
    for slug, app_name in KNOWN_APP_SLUGS:
        if slug in target_str:
            return app_name
    return "Infraestrutura Compartilhada"

def correlate_and_classify_resources(resources: List[ResourceRecord]) -> Tuple[List[ResourceRecord], List[ApplicationCluster]]:
    cluster_map: Dict[str, ApplicationCluster] = {}

    for rec in resources:
        if _is_governance(rec):
            rec.macro_domain = "Governança"
            rec.inferred_app = "Governança & Segurança"
        else:
            app_name = _infer_app_name(rec)
            rec.inferred_app = app_name
            if app_name != "Infraestrutura Compartilhada":
                rec.macro_domain = "Aplicação"
            else:
                rec.macro_domain = "Infraestrutura Compartilhada"

            if app_name not in ("Infraestrutura Compartilhada", "Governança & Segurança"):
                if app_name not in cluster_map:
                    cluster_map[app_name] = ApplicationCluster(
                        name=app_name,
                        slug=app_name.lower().replace(" / ", "-").replace(" ", "-"),
                        resources=[]
                    )
                cl = cluster_map[app_name]
                cl.resources.append(rec)
                
                # Link compute, load balancers, etc.
                ident = rec.identifier
                if "instance" in rec.resource_type:
                    cl.compute_instances.append(ident)
                elif "loadbalancer" in rec.resource_type or "LoadBalancer" in rec.cfn_resource_type:
                    cl.load_balancers.append(ident)
                elif "targetgroup" in rec.resource_type or "TargetGroup" in rec.cfn_resource_type:
                    cl.target_groups.append(ident)
                elif rec.service in ("rds", "memorydb", "elasticache"):
                    cl.databases.append(ident)
                elif rec.service == "secretsmanager":
                    cl.secrets.append(ident)
                elif rec.service == "s3":
                    cl.storage_buckets.append(ident)

    return resources, list(cluster_map.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_correlator.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/correlator.py tests/test_correlator.py
git commit -m "feat(correlator): implement governance isolation and semantic application clustering"
```

---

### Task 4: FinOps Advisory Rule Engine (`src/finops.py`)

**Files:**
- Create: `src/finops.py`
- Test: `tests/test_finops.py`

**Interfaces:**
- Consumes: `list[ResourceRecord]` from `src.models`
- Produces: `evaluate_finops_rules(resources: list[ResourceRecord]) -> list[ResourceRecord]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_finops.py
import pytest
from src.models import ResourceRecord
from src.finops import evaluate_finops_rules

def test_finops_advisory_rules():
    records = [
        ResourceRecord(
            identifier="teste123canais",
            arn="arn:aws:s3:::teste123canais",
            resource_type="s3:bucket",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::S3::Bucket",
            last_reported_at="2026-10-10",
            service="s3",
            tags="0",
            macro_domain="Aplicação"
        ),
        ResourceRecord(
            identifier="app/alb-public/123",
            arn="arn:aws:elasticloadbalancing:ca-central-1:123:loadbalancer/app/alb-public/123",
            resource_type="elasticloadbalancing:loadbalancer",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
            last_reported_at="2026-10-10",
            service="elasticloadbalancing",
            tags="0",
            macro_domain="Aplicação"
        ),
        ResourceRecord(
            identifier="eipalloc-12345",
            arn="arn:aws:ec2:ca-central-1:123:elastic-ip/eipalloc-12345",
            resource_type="ec2:elastic-ip",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::EC2::EIP",
            last_reported_at="2026-10-10",
            service="ec2",
            tags="0",
            macro_domain="Infraestrutura Compartilhada"
        ),
        ResourceRecord(
            identifier="config-rule-abc",
            arn="arn:aws:config:us-east-1:123:config-rule/abc",
            resource_type="config:config-rule",
            region="us-east-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::Config::ConfigRule",
            last_reported_at="2026-10-10",
            service="config",
            tags="0",
            macro_domain="Governança"
        )
    ]
    
    evaluated = evaluate_finops_rules(records)
    
    s3_rec = next(r for r in evaluated if r.identifier == "teste123canais")
    assert s3_rec.finops_suggestion == "Investigar (Possível Teste / Temporário)"
    assert s3_rec.finops_cost_impact == "Médio"
    
    alb_rec = next(r for r in evaluated if "alb-public" in r.identifier)
    assert alb_rec.finops_suggestion == "Investigar (Possível Órfão / Ocioso)"
    assert alb_rec.finops_cost_impact == "Alto"
    
    eip_rec = next(r for r in evaluated if r.identifier == "eipalloc-12345")
    assert eip_rec.finops_suggestion == "Investigar (Possível Órfão / Ocioso)"
    
    gov_rec = next(r for r in evaluated if r.identifier == "config-rule-abc")
    assert gov_rec.finops_suggestion == "Manter (Governança)"
    assert gov_rec.finops_cost_impact == "Baixo/Zero"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_finops.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.finops'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/finops.py
import re
from typing import List
from src.models import ResourceRecord

TEST_KEYWORDS = [r"teste", r"test\b", r"temp", r"dummy", r"sample"]

def evaluate_finops_rules(resources: List[ResourceRecord]) -> List[ResourceRecord]:
    for rec in resources:
        ident_lower = rec.identifier.lower()
        
        # 1. Governança
        if rec.macro_domain == "Governança":
            rec.finops_suggestion = "Manter (Governança)"
            rec.finops_cost_impact = "Baixo/Zero"
            rec.finops_rationale = "Recurso mandatório de baseline, segurança ou governança corporativa da organização."
            continue

        # 2. Testes / Temporários
        is_test = any(re.search(pat, ident_lower) for pat in TEST_KEYWORDS)
        if is_test:
            rec.finops_suggestion = "Investigar (Possível Teste / Temporário)"
            rec.finops_cost_impact = "Médio" if rec.service in ("s3", "ec2", "rds") else "Baixo/Zero"
            rec.finops_rationale = "Nome do recurso indica criação pontual para teste/validação; verificar se o teste já foi finalizado para exclusão."
            continue

        # 3. ALBs / Load Balancers em dev
        if "loadbalancer" in rec.resource_type or "LoadBalancer" in rec.cfn_resource_type:
            rec.finops_suggestion = "Investigar (Possível Órfão / Ocioso)"
            rec.finops_cost_impact = "Alto"
            rec.finops_rationale = (
                "ALB identificado em ambiente dev. Na AWS, cada ALB custa ~$20-$25/mês fixo. "
                "Avaliar se possui tráfego real ou se pode ser consolidado via regras de rota num ALB compartilhado."
            )
            continue

        # 4. Elastic IPs
        if "elastic-ip" in rec.resource_type or "EIP" in rec.cfn_resource_type:
            rec.finops_suggestion = "Investigar (Possível Órfão / Ocioso)"
            rec.finops_cost_impact = "Médio"
            rec.finops_rationale = (
                "Elastic IP alocado. EIPs desassociados de instâncias ativas sofrem cobrança contínua por hora. "
                "Validar se está acoplado a uma instância rodando."
            )
            continue

        # 5. Snapshots e AMIs
        if rec.resource_type in ("ec2:snapshot", "ec2:image"):
            rec.finops_suggestion = "Investigar (Possível Órfão / Ocioso)"
            rec.finops_cost_impact = "Médio"
            rec.finops_rationale = "Snapshots e AMIs acumulam custos de armazenamento EBS; validar necessidade de retenção."
            continue

        # 6. Usuários e grupos de cache sem cluster
        if rec.service in ("memorydb", "elasticache") and rec.resource_type != "cluster":
            rec.finops_suggestion = "Investigar (Possível Órfão / Ocioso)"
            rec.finops_cost_impact = "Baixo/Zero"
            rec.finops_rationale = "Configuração ou usuário residual de banco em memória sem cluster ativo associado."
            continue

        # 7. Cargas em Operação padrão
        if rec.macro_domain == "Aplicação":
            rec.finops_suggestion = "Manter (Em Operação)"
            rec.finops_cost_impact = "Alto" if rec.service in ("rds", "ec2") else "Médio"
            rec.finops_rationale = "Componente associado a uma aplicação ativa identificada no mapeamento topológico."
        else:
            rec.finops_suggestion = "Manter (Em Operação)"
            rec.finops_cost_impact = "Baixo/Zero"
            rec.finops_rationale = "Recurso de infraestrutura compartilhada (ex.: VPC, rede, DNS ou chave KMS)."

    return resources
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_finops.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/finops.py tests/test_finops.py
git commit -m "feat(finops): implement advisory rules engine with cost impact and rationales"
```

---

### Task 5: Markdown Report Exporter (`src/exporters/markdown.py`)

**Files:**
- Create: `src/exporters/__init__.py`
- Create: `src/exporters/markdown.py`
- Test: `tests/test_markdown_exporter.py`

**Interfaces:**
- Consumes: `InventoryReportData` from `src.models`
- Produces: `generate_markdown_report(report_data: InventoryReportData, output_file: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_markdown_exporter.py
import pytest
from pathlib import Path
from src.models import InventoryReportData, ApplicationCluster, ResourceRecord
from src.exporters.markdown import generate_markdown_report

def test_markdown_report_generation(tmp_path: Path):
    rec = ResourceRecord(
        identifier="canaisdb-02",
        arn="arn:aws:rds:ca-central-1:123:db:canaisdb-02",
        resource_type="rds:db",
        region="ca-central-1",
        aws_account="123",
        application_raw="-",
        cfn_resource_type="AWS::RDS::DBInstance",
        last_reported_at="2026-10-10",
        service="rds",
        tags="0",
        macro_domain="Aplicação",
        inferred_app="Canais Digitais",
        finops_suggestion="Manter (Em Operação)",
        finops_cost_impact="Alto",
        finops_rationale="Banco RDS ativo"
    )
    cluster = ApplicationCluster(
        name="Canais Digitais",
        slug="canais-dig",
        resources=[rec],
        compute_instances=[],
        load_balancers=["app/alb-canais-dig-1"],
        target_groups=["tg-canais-dig-1"],
        databases=["canaisdb-02"],
        secrets=["canais-db-01"],
        storage_buckets=["logs-canaisdig"]
    )
    data = InventoryReportData(
        account_id="123",
        total_resources=1,
        unique_arns=1,
        regions={"ca-central-1": 1},
        services={"rds": 1},
        macro_domains={"Aplicação": 1},
        finops_summary={"Manter (Em Operação)": 1},
        clusters=[cluster],
        all_resources=[rec]
    )
    
    out_file = tmp_path / "relatorio.md"
    content = generate_markdown_report(data, str(out_file))
    
    assert out_file.exists()
    assert "# Relatório Executivo de Inventário AWS e FinOps" in content
    assert "Canais Digitais" in content
    assert "canaisdb-02" in content
    assert "ca-central-1" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_markdown_exporter.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.exporters'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/exporters/__init__.py
"""Exporters package."""

# src/exporters/markdown.py
from pathlib import Path
from src.models import InventoryReportData

def generate_markdown_report(data: InventoryReportData, output_file: str) -> str:
    md = []
    md.append(f"# Relatório Executivo de Inventário AWS e FinOps — Conta {data.account_id}\n")
    md.append("> **Aviso Legal:** Todas as classificações de FinOps constituem sugestões consultivas para suporte à auditoria do time técnico e não devem ser executadas sem validação prévia de negócio.\n")
    
    # 1. Sumário Executivo
    md.append("## 1. Sumário Executivo")
    md.append(f"- **Total de Recursos Únicos Analisados:** `{data.total_resources}`")
    md.append(f"- **Conta AWS:** `{data.account_id}`")
    md.append(f"- **Regiões Detectadas:** {', '.join(f'`{r}` ({c})' for r, c in sorted(data.regions.items(), key=lambda x: x[1], reverse=True))}")
    md.append(f"- **Divisão Macro por Domínio:**")
    for dom, count in data.macro_domains.items():
        md.append(f"  - **{dom}:** `{count}` recursos")
    md.append("")

    # 2. Painel FinOps
    md.append("## 2. Painel de Sugestões FinOps")
    md.append("| Sugestão FinOps | Quantidade de Recursos |")
    md.append("| :--- | :--- |")
    for sug, count in data.finops_summary.items():
        md.append(f"| **{sug}** | `{count}` |")
    md.append("")

    # 3. Aplicações Descobertas
    md.append("## 3. Mapeamento de Aplicações e Cargas em Computação")
    for cl in data.clusters:
        md.append(f"### Aplicação: {cl.name}")
        md.append(f"- **Total de Recursos Mapeados:** `{len(cl.resources)}`")
        if cl.load_balancers:
            md.append(f"- **Load Balancers (ALBs):** {', '.join(f'`{lb}`' for lb in cl.load_balancers)}")
        if cl.target_groups:
            md.append(f"- **Target Groups:** {', '.join(f'`{tg}`' for tg in cl.target_groups)}")
        if cl.compute_instances:
            md.append(f"- **Instâncias EC2:** {', '.join(f'`{i}`' for i in cl.compute_instances)}")
        if cl.databases:
            md.append(f"- **Bancos de Dados:** {', '.join(f'`{db}`' for db in cl.databases)}")
        if cl.secrets:
            md.append(f"- **Secrets Manager:** {', '.join(f'`{s}`' for s in cl.secrets)}")
        if cl.storage_buckets:
            md.append(f"- **Buckets S3:** {', '.join(f'`{b}`' for b in cl.storage_buckets)}")
        md.append("")

    # 4. Ações Prioritárias de Investigação
    md.append("## 4. Oportunidades Prioritárias de Otimização (Quick Wins)")
    investigate_items = [r for r in data.all_resources if "Investigar" in r.finops_suggestion and r.finops_cost_impact in ("Alto", "Médio")]
    if investigate_items:
        md.append("| Recurso | Tipo / Serviço | Região | Impacto | Justificativa |")
        md.append("| :--- | :--- | :--- | :--- | :--- |")
        for r in investigate_items[:20]:
            md.append(f"| `{r.identifier}` | `{r.cfn_resource_type or r.resource_type}` | `{r.region}` | **{r.finops_cost_impact}** | {r.finops_rationale} |")
        if len(investigate_items) > 20:
            md.append(f"\n*(Mostrando 20 de {len(investigate_items)} itens de atenção; veja lista completa na planilha Excel)*")
    else:
        md.append("Nenhum recurso de alto ou médio impacto necessitando de investigação imediata.")
    md.append("")

    # 5. Guia de Uso em Novas Contas
    md.append("## 5. Instruções para Reutilização em Outras Contas")
    md.append("Para rodar esta análise em outras contas AWS exportadas:")
    md.append("```bash")
    md.append("python -m src.main --input-dir \"/caminho/para/csvs\" --output-dir \"/caminho/para/saida\"")
    md.append("```")

    full_text = "\n".join(md)
    Path(output_file).write_text(full_text, encoding="utf-8")
    return full_text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_markdown_exporter.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/exporters/__init__.py src/exporters/markdown.py tests/test_markdown_exporter.py
git commit -m "feat(exporters): implement executive Markdown report generator"
```

---

### Task 6: Excel Workbook Exporter (`src/exporters/excel.py`)

**Files:**
- Create: `src/exporters/excel.py`
- Test: `tests/test_excel_exporter.py`

**Interfaces:**
- Consumes: `InventoryReportData` from `src.models`
- Produces: `generate_excel_workbook(data: InventoryReportData, output_file: str) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_excel_exporter.py
import pytest
from pathlib import Path
import openpyxl
from src.models import InventoryReportData, ApplicationCluster, ResourceRecord
from src.exporters.excel import generate_excel_workbook

def test_excel_workbook_generation(tmp_path: Path):
    rec = ResourceRecord(
        identifier="canaisdb-02",
        arn="arn:aws:rds:ca-central-1:123:db:canaisdb-02",
        resource_type="rds:db",
        region="ca-central-1",
        aws_account="123",
        application_raw="-",
        cfn_resource_type="AWS::RDS::DBInstance",
        last_reported_at="2026-10-10",
        service="rds",
        tags="0",
        macro_domain="Aplicação",
        inferred_app="Canais Digitais",
        finops_suggestion="Investigar (Possível Órfão / Ocioso)",
        finops_cost_impact="Alto",
        finops_rationale="Validar RDS"
    )
    data = InventoryReportData(
        account_id="123",
        total_resources=1,
        unique_arns=1,
        regions={"ca-central-1": 1},
        services={"rds": 1},
        macro_domains={"Aplicação": 1},
        finops_summary={"Investigar (Possível Órfão / Ocioso)": 1},
        clusters=[],
        all_resources=[rec]
    )
    
    out_file = tmp_path / "inventario.xlsx"
    generate_excel_workbook(data, str(out_file))
    
    assert out_file.exists()
    wb = openpyxl.load_workbook(out_file)
    expected_sheets = [
        "Resumo Executivo",
        "FinOps & Ações do Time",
        "Aplicações & Compute",
        "Bancos & Armazenamento",
        "Governança & Segurança",
        "Inventário Geral"
    ]
    for s in expected_sheets:
        assert s in wb.sheetnames
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_excel_exporter.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.exporters.excel'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/exporters/excel.py
from pathlib import Path
from typing import List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from src.models import InventoryReportData, ResourceRecord

HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Calibri", size=14, bold=True, color="1F4E79")
BORDER_THIN = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9")
)

def _style_header(ws, row_idx: int, num_cols: int):
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row_idx, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

def _autofit_columns(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 60)

def generate_excel_workbook(data: InventoryReportData, output_file: str) -> None:
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # 1. Resumo Executivo
    ws_resumo = wb.create_sheet(title="Resumo Executivo")
    ws_resumo.cell(row=1, column=1, value=f"Inventário AWS & FinOps — Conta {data.account_id}").font = TITLE_FONT
    ws_resumo.cell(row=3, column=1, value="Métrica").font = HEADER_FONT
    ws_resumo.cell(row=3, column=2, value="Valor").font = HEADER_FONT
    ws_resumo.cell(row=3, column=1).fill = HEADER_FILL
    ws_resumo.cell(row=3, column=2).fill = HEADER_FILL
    
    metrics = [
        ("Total de Recursos Canônicos", data.total_resources),
        ("Total de ARNs Únicos", data.unique_arns),
        ("Conta AWS Analisada", data.account_id)
    ]
    for idx, (m, v) in enumerate(metrics, start=4):
        ws_resumo.cell(row=idx, column=1, value=m)
        ws_resumo.cell(row=idx, column=2, value=v)

    # Sugestões FinOps table
    ws_resumo.cell(row=8, column=1, value="Sugestão FinOps").font = HEADER_FONT
    ws_resumo.cell(row=8, column=2, value="Quantidade").font = HEADER_FONT
    ws_resumo.cell(row=8, column=1).fill = HEADER_FILL
    ws_resumo.cell(row=8, column=2).fill = HEADER_FILL
    for idx, (sug, count) in enumerate(data.finops_summary.items(), start=9):
        ws_resumo.cell(row=idx, column=1, value=sug)
        ws_resumo.cell(row=idx, column=2, value=count)
    _autofit_columns(ws_resumo)

    # Helper for tabular resource sheets
    def _create_resource_table(sheet_name: str, records: List[ResourceRecord], is_finops_action: bool = False):
        ws = wb.create_sheet(title=sheet_name)
        if is_finops_action:
            headers = [
                "Identificador", "Serviço", "Região", "Aplicação Inferida",
                "Sugestão FinOps", "Impacto de Custo", "Justificativa da Sugestão",
                "Decisão do Time (Manter/Deletar/Em Análise)", "Responsável", "Observações do Time"
            ]
        else:
            headers = [
                "Identificador", "ARN", "Tipo de Recurso", "Região", "Serviço",
                "Domínio", "Aplicação Inferida", "Sugestão FinOps", "Impacto", "Arquivos de Origem"
            ]
        
        ws.append(headers)
        _style_header(ws, 1, len(headers))
        
        for r in records:
            if is_finops_action:
                ws.append([
                    r.identifier, r.service, r.region, r.inferred_app,
                    r.finops_suggestion, r.finops_cost_impact, r.finops_rationale,
                    "", "", ""
                ])
            else:
                ws.append([
                    r.identifier, r.arn, r.cfn_resource_type or r.resource_type, r.region, r.service,
                    r.macro_domain, r.inferred_app, r.finops_suggestion, r.finops_cost_impact,
                    ", ".join(r.source_files)
                ])
        ws.auto_filter.ref = ws.dimensions
        _autofit_columns(ws)

    # 2. FinOps & Ações do Time
    finops_records = [r for r in data.all_resources if "Investigar" in r.finops_suggestion]
    _create_resource_table("FinOps & Ações do Time", finops_records, is_finops_action=True)

    # 3. Aplicações & Compute
    app_records = [r for r in data.all_resources if r.macro_domain == "Aplicação" or r.service in ("ec2", "elasticloadbalancing")]
    _create_resource_table("Aplicações & Compute", app_records)

    # 4. Bancos & Armazenamento
    storage_records = [r for r in data.all_resources if r.service in ("rds", "s3", "secretsmanager", "elasticache", "memorydb")]
    _create_resource_table("Bancos & Armazenamento", storage_records)

    # 5. Governança & Segurança
    gov_records = [r for r in data.all_resources if r.macro_domain == "Governança"]
    _create_resource_table("Governança & Segurança", gov_records)

    # 6. Inventário Geral
    _create_resource_table("Inventário Geral", data.all_resources)

    wb.save(output_file)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_excel_exporter.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/exporters/excel.py tests/test_excel_exporter.py
git commit -m "feat(exporters): implement openpyxl Excel exporter with multi-sheet audit tabs"
```

---

### Task 7: CLI Entrypoint & Pipeline Orchestration (`src/main.py`)

**Files:**
- Create: `src/main.py`
- Test: `tests/test_e2e.py`

**Interfaces:**
- Consumes: CLI args (`--input-dir`, `--output-dir`, `--account`), calls `ingestion`, `correlator`, `finops`, `exporters.excel`, `exporters.markdown`
- Produces: Executable CLI returning code 0 and generated artifacts.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_e2e.py
import pytest
from pathlib import Path
from src.main import run_pipeline

def test_run_pipeline_end_to_end(tmp_path: Path):
    csv_file = tmp_path / "resources.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row = "alb-test,arn:aws:elasticloadbalancing:ca-central-1:807445251352:loadbalancer/app/alb-test/1,elasticloadbalancing:loadbalancer,ca-central-1,807445251352,-,AWS::ElasticLoadBalancingV2::LoadBalancer,2026-10-10,elasticloadbalancing,0\n"
    csv_file.write_text(header + row, encoding="utf-8")
    
    out_dir = tmp_path / "output"
    
    excel_path, md_path = run_pipeline(
        input_dir=str(tmp_path),
        output_dir=str(out_dir),
        account="multicanais-dev"
    )
    
    assert Path(excel_path).exists()
    assert Path(md_path).exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_e2e.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.main'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/main.py
import argparse
import sys
from pathlib import Path
from collections import Counter
from typing import Tuple

from src.ingestion import load_and_deduplicate_csvs
from src.correlator import correlate_and_classify_resources
from src.finops import evaluate_finops_rules
from src.exporters.excel import generate_excel_workbook
from src.exporters.markdown import generate_markdown_report
from src.models import InventoryReportData

def run_pipeline(input_dir: str, output_dir: str, account: str = "") -> Tuple[str, str]:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"[*] Lendo e desduplicando CSVs em: {input_dir}")
    resources = load_and_deduplicate_csvs(input_dir)
    print(f"[+] Total de recursos canônicos consolidados: {len(resources)}")

    if not resources:
        raise ValueError(f"Nenhum recurso encontrado no diretório: {input_dir}")

    account_id = account or resources[0].aws_account or "aws-account"

    print("[*] Correlacionando recursos e inferindo aplicações...")
    resources, clusters = correlate_and_classify_resources(resources)
    print(f"[+] Aplicações detectadas: {len(clusters)} clusters ({', '.join(c.name for c in clusters)})")

    print("[*] Avaliando matriz de regras FinOps...")
    resources = evaluate_finops_rules(resources)

    # Compute summaries
    regions = Counter(r.region for r in resources)
    services = Counter(r.service for r in resources)
    macro_domains = Counter(r.macro_domain for r in resources)
    finops_summary = Counter(r.finops_suggestion for r in resources)

    report_data = InventoryReportData(
        account_id=account_id,
        total_resources=len(resources),
        unique_arns=len(set(r.arn for r in resources if r.arn)),
        regions=dict(regions),
        services=dict(services),
        macro_domains=dict(macro_domains),
        finops_summary=dict(finops_summary),
        clusters=clusters,
        all_resources=resources
    )

    clean_account_name = account_id.replace(" ", "_")
    excel_file = str(out_path / f"inventario_{clean_account_name}.xlsx")
    md_file = str(out_path / f"relatorio_{clean_account_name}.md")

    print(f"[*] Gerando pasta de trabalho Excel: {excel_file}")
    generate_excel_workbook(report_data, excel_file)

    print(f"[*] Gerando relatório executivo Markdown: {md_file}")
    generate_markdown_report(report_data, md_file)

    print("[✓] Processamento concluído com sucesso!")
    return excel_file, md_file

def main():
    parser = argparse.ArgumentParser(description="Mapeador de Recursos AWS e FinOps Pipeline")
    parser.add_argument("--input-dir", default="./", help="Diretório contendo os arquivos CSV de exportação")
    parser.add_argument("--output-dir", default="./output", help="Diretório de saída para os relatórios gerados")
    parser.add_argument("--account", default="multicanais-dev", help="Nome ou ID da conta AWS para titulação")
    args = parser.parse_args()

    try:
        run_pipeline(args.input_dir, args.output_dir, args.account)
    except Exception as e:
        print(f"[!] Erro durante execução do pipeline: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_e2e.py -v`  
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`  
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/main.py tests/test_e2e.py
git commit -m "feat(main): implement CLI entrypoint and end-to-end pipeline execution"
```

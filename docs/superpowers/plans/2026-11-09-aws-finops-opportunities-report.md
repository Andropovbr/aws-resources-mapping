# Implementação: Relatório Executivo de Oportunidades FinOps e Playbooks de Investigação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expandir a ferramenta de auditoria AWS com um motor analítico de oportunidades FinOps e um gerador de relatório executivo dedicado (`relatorio_oportunidades_finops_<conta>.md`), contemplando padrões de consumo, superdimensionamento, redução de custos e playbooks de investigação com comandos AWS CLI para recursos sem telemetria direta.

**Architecture:** Módulo analítico desacoplado (`src/finops_analyzer.py`) que processa o `InventoryReportData` gerado pela etapa de correlação, sintetiza oportunidades nos três eixos da demanda, gera playbooks acionáveis para itens `[NECESSITA ANÁLISE]` e delega a renderização para um exporter executivo independente (`src/exporters/finops_report.py`), integrado diretamente ao fluxo principal (`src/main.py`).

**Tech Stack:** Python 3.10+, Dataclasses, Pytest, Markdown.

**Spec:** `docs/superpowers/specs/2026-11-09-aws-finops-opportunities-report-design.md`

## Global Constraints

- Todos os novos modelos devem ser dataclasses em `src/models.py`.
- Nenhum dado de recurso com telemetria ausente pode ser descartado; deve receber status `[NECESSITA ANÁLISE]` e um playbook de investigação associado.
- Os comandos de terminal devem ser gerados em sintaxe válida de AWS CLI, parametrizados com a região e identificadores reais extraídos da conta.
- Cálculos de proporção e métricas não podem lançar `ZeroDivisionError` ou exceções quando a conta tiver zero instâncias de um determinado serviço.
- Todos os testes devem rodar via `python -m pytest` e passar com 100% de sucesso.

---

### Task 1: FinOps Opportunity Data Models

**Files:**
- Modify: `src/models.py:35-46`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `ResourceRecord`, `InventoryReportData` de `src/models.py`.
- Produces: `PlaybookGuide`, `FinOpsOpportunity`, `FinOpsAnalysisResult` em `src/models.py`.

- [ ] **Step 1: Escrever teste unitário para os novos modelos de dados**

Adicionar ao final de `tests/test_models.py`:

```python
from src.models import PlaybookGuide, FinOpsOpportunity, FinOpsAnalysisResult

def test_finops_opportunity_models():
    guide = PlaybookGuide(
        playbook_id="pb-ec2-rightsizing",
        title="Playbook 1: EC2 Right-sizing",
        target_metric="CPUUtilization < 10%",
        target_resources=["i-090d9b01ccf2af5ae"],
        console_path="CloudWatch > Metrics > EC2",
        aws_cli_command="aws cloudwatch get-metric-statistics ...",
        decision_criteria="Se CPU < 10%, reduzir instância",
        recommended_action="Fazer downgrade de t3.large para t3.small"
    )
    assert guide.playbook_id == "pb-ec2-rightsizing"
    assert len(guide.target_resources) == 1

    opp = FinOpsOpportunity(
        pillar="Superdimensionamento",
        title="Desproporção de ALBs vs Instâncias EC2",
        description="9 ALBs para 2 instâncias EC2 mapeadas",
        evidence_status="[AÇÃO IMEDIATA]",
        effort_level="Baixo (Quick Win)",
        impact_level="Alto",
        estimated_monthly_savings_usd=157.5,
        affected_resources_count=9,
        resource_identifiers=["app/Docker-dev/6de4d3f3d608fb4c"],
        playbook_id=None
    )
    assert opp.pillar == "Superdimensionamento"
    assert opp.estimated_monthly_savings_usd == 157.5

    result = FinOpsAnalysisResult(
        account_id="multicanais-dev",
        total_opportunities=1,
        immediate_actions_count=1,
        needs_analysis_count=0,
        total_estimated_monthly_savings_usd=157.5,
        pillar_consumption_opportunities=[],
        pillar_rightsizing_opportunities=[opp],
        pillar_cost_reduction_opportunities=[],
        playbooks=[guide]
    )
    assert result.total_opportunities == 1
    assert len(result.playbooks) == 1
```

- [ ] **Step 2: Executar o teste e verificar a falha**

Run: `python -m pytest tests/test_models.py::test_finops_opportunity_models -v`  
Expected: FAIL com `ImportError: cannot import name 'PlaybookGuide' from 'src.models'`

- [ ] **Step 3: Implementar os modelos em `src/models.py`**

Em `src/models.py`, adicionar:

```python
from typing import List, Dict, Optional

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
```

- [ ] **Step 4: Executar o teste e verificar o sucesso**

Run: `python -m pytest tests/test_models.py -v`  
Expected: PASS com 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat(models): add FinOpsOpportunity, PlaybookGuide and FinOpsAnalysisResult models"
```

---

### Task 2: FinOps Opportunities & Playbook Analyzer

**Files:**
- Create: `src/finops_analyzer.py`
- Test: `tests/test_finops_analyzer.py`

**Interfaces:**
- Consumes: `InventoryReportData`, `ResourceRecord`, `PlaybookGuide`, `FinOpsOpportunity`, `FinOpsAnalysisResult` de `src/models.py`.
- Produces: `analyze_finops_opportunities(report_data: InventoryReportData) -> FinOpsAnalysisResult`.

- [ ] **Step 1: Escrever testes unitários para as regras heurísticas e playbooks**

Criar `tests/test_finops_analyzer.py`:

```python
import pytest
from src.models import ResourceRecord, InventoryReportData, ApplicationCluster
from src.finops_analyzer import analyze_finops_opportunities

def create_sample_report_data(alb_count=9, ec2_count=2, rds_count=2, regions=None):
    if regions is None:
        regions = {"ca-central-1": 10, "sa-east-1": 10, "us-west-2": 2, "ap-northeast-2": 1}
    
    resources = []
    # ALBs
    for i in range(alb_count):
        resources.append(ResourceRecord(
            identifier=f"app/alb-{i}/abc{i}",
            arn=f"arn:aws:elasticloadbalancing:ca-central-1:807445251352:loadbalancer/app/alb-{i}/abc{i}",
            resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
            region="ca-central-1",
            aws_account="807445251352",
            application_raw="-",
            cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
            last_reported_at="2026-10-10",
            service="elasticloadbalancing",
            tags="0",
            macro_domain="Aplicação"
        ))
    # EC2
    for i in range(ec2_count):
        resources.append(ResourceRecord(
            identifier=f"i-00000000{i}",
            arn=f"arn:aws:ec2:ca-central-1:807445251352:instance/i-00000000{i}",
            resource_type="ec2:instance",
            region="ca-central-1",
            aws_account="807445251352",
            application_raw="-",
            cfn_resource_type="AWS::EC2::Instance",
            last_reported_at="2026-10-10",
            service="ec2",
            tags="0",
            macro_domain="Aplicação"
        ))
    # RDS
    for i in range(rds_count):
        resources.append(ResourceRecord(
            identifier=f"canaisdb-0{i}",
            arn=f"arn:aws:rds:ca-central-1:807445251352:db:canaisdb-0{i}",
            resource_type="AWS::RDS::DBInstance",
            region="ca-central-1",
            aws_account="807445251352",
            application_raw="-",
            cfn_resource_type="AWS::RDS::DBInstance",
            last_reported_at="2026-10-10",
            service="rds",
            tags="0",
            macro_domain="Aplicação"
        ))
    # Test Snapshot
    resources.append(ResourceRecord(
        identifier="snapshot-copy-test",
        arn="arn:aws:rds:sa-east-1:807445251352:snapshot:snapshot-copy-test",
        resource_type="AWS::RDS::DBSnapshot",
        region="sa-east-1",
        aws_account="807445251352",
        application_raw="-",
        cfn_resource_type="AWS::RDS::DBSnapshot",
        last_reported_at="2026-10-10",
        service="rds",
        tags="0",
        macro_domain="Infraestrutura Compartilhada"
    ))
    # Unassociated EIP
    resources.append(ResourceRecord(
        identifier="eipalloc-123456",
        arn="arn:aws:ec2:ca-central-1:807445251352:elastic-ip/eipalloc-123456",
        resource_type="AWS::EC2::EIP",
        region="ca-central-1",
        aws_account="807445251352",
        application_raw="-",
        cfn_resource_type="AWS::EC2::EIP",
        last_reported_at="2026-10-10",
        service="ec2",
        tags="0",
        macro_domain="Infraestrutura Compartilhada"
    ))

    return InventoryReportData(
        account_id="multicanais-dev",
        total_resources=len(resources),
        unique_arns=len(resources),
        regions=regions,
        services={"elasticloadbalancing": alb_count, "ec2": ec2_count + 1, "rds": rds_count + 1},
        macro_domains={"Aplicação": alb_count + ec2_count + rds_count, "Infraestrutura Compartilhada": 2},
        finops_summary={"Manter (Em Operação)": 10, "Investigar (Possível Órfão / Ocioso)": 2},
        clusters=[],
        all_resources=resources
    )

def test_analyze_finops_opportunities_disproportion_and_playbooks():
    report_data = create_sample_report_data(alb_count=9, ec2_count=2)
    analysis = analyze_finops_opportunities(report_data)

    assert analysis.account_id == "multicanais-dev"
    assert analysis.total_opportunities >= 3
    assert analysis.immediate_actions_count >= 1
    assert analysis.needs_analysis_count >= 1
    assert analysis.total_estimated_monthly_savings_usd > 100.0

    # Verificar oportunidade de desproporção de ALBs
    alb_opp = next((o for o in analysis.pillar_rightsizing_opportunities if "ALB" in o.title), None)
    assert alb_opp is not None
    assert alb_opp.evidence_status == "[AÇÃO IMEDIATA]"
    assert alb_opp.affected_resources_count == 9

    # Verificar que playbooks foram montados
    assert len(analysis.playbooks) >= 3
    ec2_pb = next((p for p in analysis.playbooks if "EC2" in p.title), None)
    assert ec2_pb is not None
    assert "i-000000000" in ec2_pb.target_resources
    assert "aws compute-optimizer get-ec2-instance-recommendations" in ec2_pb.aws_cli_command

def test_analyze_finops_opportunities_zero_division_guard():
    # Garantir que 0 instâncias EC2 não gere ZeroDivisionError
    report_data = create_sample_report_data(alb_count=3, ec2_count=0)
    analysis = analyze_finops_opportunities(report_data)
    assert analysis is not None
    alb_opp = next((o for o in analysis.pillar_rightsizing_opportunities if "ALB" in o.title), None)
    assert alb_opp is not None
```

- [ ] **Step 2: Executar o teste e verificar a falha**

Run: `python -m pytest tests/test_finops_analyzer.py -v`  
Expected: FAIL com `ModuleNotFoundError: No module named 'src.finops_analyzer'`

- [ ] **Step 3: Implementar `src/finops_analyzer.py`**

Criar `src/finops_analyzer.py`:

```python
import re
from typing import List, Dict, Optional
from src.models import (
    ResourceRecord,
    InventoryReportData,
    PlaybookGuide,
    FinOpsOpportunity,
    FinOpsAnalysisResult
)

def analyze_finops_opportunities(report_data: InventoryReportData) -> FinOpsAnalysisResult:
    consumption_opps: List[FinOpsOpportunity] = []
    rightsizing_opps: List[FinOpsOpportunity] = []
    reduction_opps: List[FinOpsOpportunity] = []
    playbooks: List[PlaybookGuide] = []

    resources = report_data.all_resources
    account_id = report_data.account_id

    # 1. Separar recursos-chave
    ec2_instances = [r for r in resources if r.service.lower() == "ec2" and "instance" in r.resource_type.lower()]
    albs = [r for r in resources if r.service.lower() == "elasticloadbalancing" and "loadbalancer" in r.resource_type.lower()]
    rds_instances = [r for r in resources if r.service.lower() == "rds" and "dbinstance" in r.resource_type.lower()]
    eips = [r for r in resources if "eip" in r.resource_type.lower() or "elastic-ip" in r.resource_type.lower()]
    snapshots = [r for r in resources if "snapshot" in r.resource_type.lower()]
    test_resources = [
        r for r in resources
        if any(re.search(pat, r.identifier.lower()) for pat in [r"teste", r"test\b", r"temp", r"dummy", r"sample"])
        and r.macro_domain != "Governança"
    ]

    # --- PILAR A: Padrões de Consumo & Anomalias ---
    # A1: Dispersão Regional
    main_regions = {"ca-central-1", "sa-east-1"}
    foreign_regions = {reg: count for reg, count in report_data.regions.items() if reg not in main_regions and reg != "global"}
    total_foreign = sum(foreign_regions.values())
    if total_foreign > 0:
        consumption_opps.append(FinOpsOpportunity(
            pillar="Padrões de Consumo",
            title="Dispersão de Recursos em Regiões Secundárias",
            description=(
                f"Foram identificados {total_foreign} recursos distribuídos em {len(foreign_regions)} regiões "
                f"secundárias fora do núcleo do projeto ({', '.join(sorted(foreign_regions.keys())[:5])}...). "
                f"Em ambiente de desenvolvimento, isso indica testes residuais ou criação não intencional."
            ),
            evidence_status="[NECESSITA ANÁLISE]",
            effort_level="Baixo (Quick Win)",
            impact_level="Médio",
            estimated_monthly_savings_usd=total_foreign * 1.5,
            affected_resources_count=total_foreign,
            resource_identifiers=[f"Regiões: {', '.join(sorted(foreign_regions.keys()))}"],
            playbook_id="pb-cross-region-cleanup"
        ))

    # A2: Regime Contínuo 24x7 em Ambiente de Desenvolvimento
    if ec2_instances or rds_instances:
        total_24x7 = len(ec2_instances) + len(rds_instances)
        # Estimativa: desligamento 12h/dia + fins de semana economiza ~60% de computação
        estimated_savings = (len(ec2_instances) * 35.0 + len(rds_instances) * 55.0) * 0.60
        consumption_opps.append(FinOpsOpportunity(
            pillar="Padrões de Consumo",
            title="Oportunidade de Regime de Horário Útil (Instance Scheduling 24x7)",
            description=(
                f"Ambiente dev possui {len(ec2_instances)} instâncias EC2 e {len(rds_instances)} instâncias RDS "
                f"em execução contínua (720h/mês). A implementação de desligamento automático noturno e aos fins de semana "
                f"(regime comercial de ~220h/mês) proporciona até 65% de redução de custo nessas cargas."
            ),
            evidence_status="[NECESSITA ANÁLISE]",
            effort_level="Médio",
            impact_level="Alto",
            estimated_monthly_savings_usd=estimated_savings,
            affected_resources_count=total_24x7,
            resource_identifiers=[r.identifier for r in ec2_instances + rds_instances],
            playbook_id="pb-dev-scheduling"
        ))

    # --- PILAR B: Recursos Superdimensionados / Right-sizing ---
    # B1: Desproporção ALBs vs Instâncias
    if albs:
        ec2_count = len(ec2_instances)
        ratio_str = f"{len(albs)}:{ec2_count}" if ec2_count > 0 else f"{len(albs)}:0"
        # Cada ALB adicional além de 2 custa ~$22.50 fixo
        surplus_albs = max(0, len(albs) - 2)
        alb_savings = surplus_albs * 22.50
        rightsizing_opps.append(FinOpsOpportunity(
            pillar="Superdimensionamento",
            title="Desproporção Crítica de Balanceadores (ALBs vs Instâncias)",
            description=(
                f"Identificados {len(albs)} Application Load Balancers para apenas {ec2_count} instâncias EC2 "
                f"(proporção {ratio_str}). Cada ALB possui custo fixo mensal de ~$20-$25 mais LCUs. "
                f"Recomenda-se consolidar os balanceadores em 1 ou 2 ALBs compartilhados utilizando roteamento por Host/Path."
            ),
            evidence_status="[AÇÃO IMEDIATA]",
            effort_level="Médio",
            impact_level="Alto",
            estimated_monthly_savings_usd=alb_savings,
            affected_resources_count=len(albs),
            resource_identifiers=[r.identifier for r in albs],
            playbook_id="pb-alb-traffic"
        ))

    # B2: Right-sizing de EC2 e RDS
    if ec2_instances:
        rightsizing_opps.append(FinOpsOpportunity(
            pillar="Superdimensionamento",
            title="Avaliação de Right-sizing de Computação EC2",
            description=(
                f"{len(ec2_instances)} instâncias EC2 ativas em dev elegíveis para ajuste fino de capacidade. "
                f"O inventário estático não possui métricas de consumo de CPU/Memória. É mandatório auditar "
                f"a telemetria antes de redimensionar."
            ),
            evidence_status="[NECESSITA ANÁLISE]",
            effort_level="Baixo (Quick Win)",
            impact_level="Médio",
            estimated_monthly_savings_usd=len(ec2_instances) * 20.0,
            affected_resources_count=len(ec2_instances),
            resource_identifiers=[r.identifier for r in ec2_instances],
            playbook_id="pb-ec2-rightsizing"
        ))

    # --- PILAR C: Serviços com Potencial de Redução de Custos ---
    # C1: Elastic IPs Ociosos
    if eips:
        eip_savings = len(eips) * 3.65
        reduction_opps.append(FinOpsOpportunity(
            pillar="Redução de Custos",
            title="Elastic IPs Desassociados ou Ociosos",
            description=(
                f"{len(eips)} Elastic IP(s) alocado(s). Na AWS, EIPs não associados a instâncias ativas sofrem "
                f"cobrança contínua por hora ($0.005/h). Validar e liberar endereços sem uso."
            ),
            evidence_status="[AÇÃO IMEDIATA]",
            effort_level="Baixo (Quick Win)",
            impact_level="Baixo",
            estimated_monthly_savings_usd=eip_savings,
            affected_resources_count=len(eips),
            resource_identifiers=[r.identifier for r in eips],
            playbook_id=None
        ))

    # C2: Snapshots e AMIs Antigos/Residuais
    if snapshots:
        reduction_opps.append(FinOpsOpportunity(
            pillar="Redução de Custos",
            title="Snapshots Manuais e Retenção Residual",
            description=(
                f"{len(snapshots)} snapshot(s) identificado(s) ocupando armazenamento contínuo. "
                f"Auditar necessidade de retenção e implementar política de expiração via AWS Backup."
            ),
            evidence_status="[AÇÃO IMEDIATA]",
            effort_level="Baixo (Quick Win)",
            impact_level="Médio",
            estimated_monthly_savings_usd=len(snapshots) * 5.0,
            affected_resources_count=len(snapshots),
            resource_identifiers=[r.identifier for r in snapshots],
            playbook_id="pb-snapshots-cleanup"
        ))

    # C3: Recursos com Nomenclatura de Teste
    if test_resources:
        reduction_opps.append(FinOpsOpportunity(
            pillar="Redução de Custos",
            title="Recursos Residuais com Nomenclatura de Teste/Temporário",
            description=(
                f"{len(test_resources)} recurso(s) com sufixo ou prefixo de teste identificado(s). "
                f"Confirmar encerramento de testes e realizar o descarte seguro."
            ),
            evidence_status="[AÇÃO IMEDIATA]",
            effort_level="Baixo (Quick Win)",
            impact_level="Médio",
            estimated_monthly_savings_usd=len(test_resources) * 8.0,
            affected_resources_count=len(test_resources),
            resource_identifiers=[r.identifier for r in test_resources],
            playbook_id=None
        ))

    # --- MONTAGEM DOS PLAYBOOKS DE INVESTIGAÇÃO ---
    primary_region = "ca-central-1" if "ca-central-1" in report_data.regions else "sa-east-1"

    # Playbook 1: EC2 Right-sizing & Compute Optimizer
    ec2_ids = [r.identifier for r in ec2_instances]
    ec2_arns = " ".join([r.arn for r in ec2_instances]) if ec2_instances else "<InstanceARNs>"
    sample_ec2 = ec2_ids[0] if ec2_ids else "<InstanceId>"
    playbooks.append(PlaybookGuide(
        playbook_id="pb-ec2-rightsizing",
        title="Playbook 1: Auditoria de Consumo e Right-sizing de Instâncias EC2",
        target_metric="CPUUtilization < 10% e MaxCPU < 30% nos últimos 14 dias",
        target_resources=ec2_ids,
        console_path="AWS Console > CloudWatch > Metrics > EC2 > Per-Instance Metrics",
        aws_cli_command=(
            f"# 1. Consultar recomendações prontas do AWS Compute Optimizer (Machine Learning):\n"
            f"aws compute-optimizer get-ec2-instance-recommendations --region {primary_region} --instance-arns {ec2_arns}\n\n"
            f"# 2. Extrair histórico de CPU média diária nos últimos 14 dias:\n"
            f"aws cloudwatch get-metric-statistics --region {primary_region} --namespace AWS/EC2 --metric-name CPUUtilization "
            f"--dimensions Name=InstanceId,Value={sample_ec2} "
            f"--start-time 2026-10-01T00:00:00Z --end-time 2026-10-15T23:59:59Z --period 86400 --statistics Average Maximum"
        ),
        decision_criteria="Se a média de CPU estiver abaixo de 10% e o pico abaixo de 25% por 14 dias contínuos.",
        recommended_action="Reduzir o tamanho da instância (downsizing para geração t4g baseada em Graviton com 20% adicional de desconto)."
    ))

    # Playbook 2: Inatividade e Consolidação de ALBs
    alb_names = [r.identifier for r in albs]
    sample_alb = alb_names[0] if alb_names else "<LoadBalancerName>"
    playbooks.append(PlaybookGuide(
        playbook_id="pb-alb-traffic",
        title="Playbook 2: Auditoria de Tráfego e Consolidação de Application Load Balancers",
        target_metric="RequestCount == 0 ou ActiveConnectionCount < 5 nos últimos 30 dias",
        target_resources=alb_names,
        console_path="AWS Console > CloudWatch > Metrics > ApplicationELB > Per AppELB Metrics",
        aws_cli_command=(
            f"# Extrair total de requisições recebidas pelo Load Balancer nos últimos 30 dias:\n"
            f"aws cloudwatch get-metric-statistics --region {primary_region} --namespace AWS/ApplicationELB "
            f"--metric-name RequestCount --dimensions Name=LoadBalancer,Value={sample_alb} "
            f"--start-time 2026-10-01T00:00:00Z --end-time 2026-10-31T23:59:59Z --period 86400 --statistics Sum"
        ),
        decision_criteria="Se a soma de requisições for zero ou residual (< 100 req/mês em dev).",
        recommended_action="Descomissionar o ALB órfão ou migrar suas rotas para o ALB consolidado compartilhado de dev."
    ))

    # Playbook 3: Agendamento Noturno de Dev (EC2 e RDS)
    rds_ids = [r.identifier for r in rds_instances]
    sample_rds = rds_ids[0] if rds_ids else "<DBInstanceIdentifier>"
    playbooks.append(PlaybookGuide(
        playbook_id="pb-dev-scheduling",
        title="Playbook 3: Auditoria de Conexões e Validação de Agendamento Noturno (Dev)",
        target_metric="DatabaseConnections == 0 fora do horário 08h-19h e nos fins de semana",
        target_resources=rds_ids,
        console_path="AWS Console > CloudWatch > Metrics > RDS > Per-Database Metrics",
        aws_cli_command=(
            f"# Verificar conexões ativas no banco de dados durante a madrugada:\n"
            f"aws cloudwatch get-metric-statistics --region {primary_region} --namespace AWS/RDS "
            f"--metric-name DatabaseConnections --dimensions Name=DBInstanceIdentifier,Value={sample_rds} "
            f"--start-time 2026-10-10T00:00:00Z --end-time 2026-10-10T23:59:59Z --period 3600 --statistics Maximum"
        ),
        decision_criteria="Se não houver conexões após as 20h e nos finais de semana.",
        recommended_action="Implantar automação de desligamento programado (AWS Instance Scheduler / Lambda com EventBridge) para 60% de economia."
    ))

    # Playbook 4: Limpeza de Snapshots Órfãos
    playbooks.append(PlaybookGuide(
        playbook_id="pb-snapshots-cleanup",
        title="Playbook 4: Auditoria de Snapshots Manuais e Retenção EBS/RDS",
        target_metric="Snapshots criados há mais de 30 dias sem vínculo com instâncias ativas",
        target_resources=[r.identifier for r in snapshots],
        console_path="AWS Console > EC2 / RDS > Snapshots",
        aws_cli_command=(
            f"# Listar snapshots manuais mais antigos na região principal:\n"
            f"aws ec2 describe-snapshots --owner-ids self --region {primary_region} "
            f"--query 'Snapshots[?StartTime<=`2026-09-01`].[SnapshotId,VolumeId,StartTime]' --output table"
        ),
        decision_criteria="Snapshots de instâncias já deletadas ou rotinas de teste finalizadas.",
        recommended_action="Excluir snapshots legados e configurar regra de ciclo de vida automática no AWS Backup."
    ))

    all_opps = consumption_opps + rightsizing_opps + reduction_opps
    immediate = sum(1 for o in all_opps if o.evidence_status == "[AÇÃO IMEDIATA]")
    needs_analysis = sum(1 for o in all_opps if o.evidence_status == "[NECESSITA ANÁLISE]")
    total_savings = sum(o.estimated_monthly_savings_usd or 0.0 for o in all_opps)

    return FinOpsAnalysisResult(
        account_id=account_id,
        total_opportunities=len(all_opps),
        immediate_actions_count=immediate,
        needs_analysis_count=needs_analysis,
        total_estimated_monthly_savings_usd=total_savings,
        pillar_consumption_opportunities=consumption_opps,
        pillar_rightsizing_opportunities=rightsizing_opps,
        pillar_cost_reduction_opportunities=reduction_opps,
        playbooks=playbooks
    )
```

- [ ] **Step 4: Executar o teste e verificar o sucesso**

Run: `python -m pytest tests/test_finops_analyzer.py -v`  
Expected: PASS com 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/finops_analyzer.py tests/test_finops_analyzer.py
git commit -m "feat(finops): implement FinOps opportunities and investigation playbooks analyzer"
```

---

### Task 3: Executive FinOps Markdown Exporter

**Files:**
- Create: `src/exporters/finops_report.py`
- Test: `tests/test_finops_report_exporter.py`

**Interfaces:**
- Consumes: `FinOpsAnalysisResult`, `FinOpsOpportunity`, `PlaybookGuide` de `src/models.py`.
- Produces: `export_finops_opportunities_markdown(analysis: FinOpsAnalysisResult, output_path: str) -> None`.

- [ ] **Step 1: Escrever teste unitário para o gerador de Markdown executivo**

Criar `tests/test_finops_report_exporter.py`:

```python
import os
import pytest
from src.models import FinOpsOpportunity, PlaybookGuide, FinOpsAnalysisResult
from src.exporters.finops_report import export_finops_opportunities_markdown

def test_export_finops_opportunities_markdown(tmp_path):
    output_file = tmp_path / "relatorio_oportunidades_finops_test.md"

    opp = FinOpsOpportunity(
        pillar="Superdimensionamento",
        title="Desproporção de ALBs",
        description="9 ALBs para 2 instâncias",
        evidence_status="[AÇÃO IMEDIATA]",
        effort_level="Baixo (Quick Win)",
        impact_level="Alto",
        estimated_monthly_savings_usd=157.50,
        affected_resources_count=9,
        resource_identifiers=["app/Docker-dev/6de4d3f3d608fb4c"],
        playbook_id="pb-alb-traffic"
    )

    guide = PlaybookGuide(
        playbook_id="pb-alb-traffic",
        title="Playbook: Tráfego de ALBs",
        target_metric="RequestCount == 0",
        target_resources=["app/Docker-dev/6de4d3f3d608fb4c"],
        console_path="CloudWatch > Metrics > ALB",
        aws_cli_command="aws cloudwatch get-metric-statistics ...",
        decision_criteria="Se zero requisições",
        recommended_action="Consolidar ALBs"
    )

    analysis = FinOpsAnalysisResult(
        account_id="multicanais-dev",
        total_opportunities=1,
        immediate_actions_count=1,
        needs_analysis_count=0,
        total_estimated_monthly_savings_usd=157.50,
        pillar_consumption_opportunities=[],
        pillar_rightsizing_opportunities=[opp],
        pillar_cost_reduction_opportunities=[],
        playbooks=[guide]
    )

    export_finops_opportunities_markdown(analysis, str(output_file))

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "Relatório Executivo de Oportunidades FinOps" in content
    assert "multicanais-dev" in content
    assert "Scorecard Executivo & Impacto Financeiro" in content
    assert "Desproporção de ALBs" in content
    assert "$157.50" in content
    assert "Playbook: Tráfego de ALBs" in content
    assert "aws cloudwatch get-metric-statistics" in content
    assert "Roadmap Recomendado de Execução" in content
```

- [ ] **Step 2: Executar o teste e verificar a falha**

Run: `python -m pytest tests/test_finops_report_exporter.py -v`  
Expected: FAIL com `ModuleNotFoundError: No module named 'src.exporters.finops_report'`

- [ ] **Step 3: Implementar `src/exporters/finops_report.py`**

Criar `src/exporters/finops_report.py`:

```python
import os
from src.models import FinOpsAnalysisResult, FinOpsOpportunity

def _format_opportunity_table(opportunities: list[FinOpsOpportunity]) -> str:
    if not opportunities:
        return "_Nenhuma oportunidade identificada neste pilar._\n\n"
    
    lines = [
        "| Status | Oportunidade | Impacto Financeiro Est. | Esforço | Recursos Afetados | Playbook / Ação |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for o in opportunities:
        savings = f"~${o.estimated_monthly_savings_usd:.2f}/mês" if o.estimated_monthly_savings_usd else "A Auditar"
        playbook_ref = f"[`{o.playbook_id}`](#{o.playbook_id})" if o.playbook_id else "Ação Direta"
        status_badge = f"**{o.evidence_status}**"
        lines.append(
            f"| {status_badge} | **{o.title}**<br>{o.description} | **{savings}** | {o.effort_level} | {o.affected_resources_count} | {playbook_ref} |"
        )
    return "\n".join(lines) + "\n\n"

def export_finops_opportunities_markdown(analysis: FinOpsAnalysisResult, output_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    annual_savings = analysis.total_estimated_monthly_savings_usd * 12

    md = []
    md.append(f"# Relatório Executivo de Oportunidades FinOps — Conta {analysis.account_id}\n")
    md.append("> **Aviso Consultivo:** Todas as estimativas financeiras e sugestões apresentadas constituem recomendações consultivas para priorização estratégica da equipe de engenharia e liderança. Nenhuma alteração destrutiva deve ser executada sem validação técnica prévia de negócio.\n")
    
    # 1. Scorecard Executivo
    md.append("## 1. Scorecard Executivo & Impacto Financeiro\n")
    md.append("| Indicador | Valor Consolidado | Observações |")
    md.append("| :--- | :--- | :--- |")
    md.append(f"| **Economia Mensal Estimada** | **~${analysis.total_estimated_monthly_savings_usd:,.2f} USD/mês** | Projeção combinada de ações diretas e agendamento |")
    md.append(f"| **Economia Anualizada Projetada** | **~${annual_savings:,.2f} USD/ano** | Projeção anual de budget liberado para inovação |")
    md.append(f"| **Total de Oportunidades** | `{analysis.total_opportunities}` | Mapeadas nos três pilares estratégicos |")
    md.append(f"| **Ações Imediatas (Quick Wins)** | `{analysis.immediate_actions_count}` | Evidência conclusiva presente no inventário |")
    md.append(f"| **Hipóteses com Playbook** | `{analysis.needs_analysis_count}` | Itens com dados parciais mantidos para validação |")
    md.append("\n")

    # Matriz de Priorização
    md.append("### Matriz de Priorização (Esforço x Impacto)\n")
    md.append("- **Quick Wins (Alto Impacto / Baixo Esforço):** Consolidação de ALBs excedentes e limpeza de recursos/snapshots residuais de teste.")
    md.append("- **Projetos Estruturais (Alto Impacto / Médio Esforço):** Implantação de agendamento automático 24x7 (Instance Scheduler) para EC2 e RDS em desenvolvimento.")
    md.append("- **Higienização Operacional (Médio/Baixo Impacto / Baixo Esforço):** Liberação de Elastic IPs soltos e encerramento de recursos em regiões não oficiais.\n\n")

    # 2. Pilar A
    md.append("## 2. Pilar A: Padrões de Consumo & Oportunidades de Agendamento\n")
    md.append(_format_opportunity_table(analysis.pillar_consumption_opportunities))

    # 3. Pilar B
    md.append("## 3. Pilar B: Recursos Superdimensionados (Right-sizing)\n")
    md.append(_format_opportunity_table(analysis.pillar_rightsizing_opportunities))

    # 4. Pilar C
    md.append("## 4. Pilar C: Serviços com Potencial de Redução de Custos\n")
    md.append(_format_opportunity_table(analysis.pillar_cost_reduction_opportunities))

    # 5. Playbooks de Investigação
    md.append("## 5. Playbooks Práticos de Investigação (Gaps de Telemetria)\n")
    md.append("Para os recursos onde o inventário estático não fornece séries temporais de consumo, utilize os roteiros e comandos AWS CLI abaixo para comprovar a ociosidade antes da tomada de decisão:\n\n")

    for pb in analysis.playbooks:
        md.append(f"<a id=\"{pb.playbook_id}\"></a>\n")
        md.append(f"### {pb.title}\n")
        md.append(f"- **Métrica-Alvo:** `{pb.target_metric}`")
        md.append(f"- **Recursos Identificados:** `{', '.join(pb.target_resources[:10])}`" + (f" _(+ {len(pb.target_resources)-10} adicionais)_" if len(pb.target_resources) > 10 else ""))
        md.append(f"- **Caminho no Console:** {pb.console_path}")
        md.append(f"- **Critério de Decisão:** {pb.decision_criteria}")
        md.append(f"- **Ação Recomendada:** {pb.recommended_action}\n")
        md.append("#### Comando AWS CLI Pronto para Copiar:")
        md.append("```bash")
        md.append(pb.aws_cli_command)
        md.append("```\n")

    # 6. Roadmap
    md.append("## 6. Roadmap Recomendado de Execução (30 / 60 / 90 Dias)\n")
    md.append("1. **Primeiros 30 Dias (Quick Wins & Validação de Telemetria):**")
    md.append("   - Executar os comandos AWS CLI do Playbook 2 para verificar tráfego dos 9 ALBs e consolidar em 1 ou 2 balanceadores.")
    md.append("   - Liberar Elastic IPs desassociados e deletar snapshots de teste.")
    md.append("2. **60 Dias (Right-sizing e Agendamento Automático):**")
    md.append("   - Rodar consulta do AWS Compute Optimizer (Playbook 1) e redimensionar instâncias superdimensionadas.")
    md.append("   - Implantar rotina de Instance Scheduler (Playbook 3) para desligamento noturno em dev.")
    md.append("3. **90 Dias (Governança Contínua):**")
    md.append("   - Estabelecer alarmes de AWS Budgets e SCPs/políticas de tag para evitar proliferação regional descontrolada.\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
```

- [ ] **Step 4: Executar o teste e verificar o sucesso**

Run: `python -m pytest tests/test_finops_report_exporter.py -v`  
Expected: PASS com 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/exporters/finops_report.py tests/test_finops_report_exporter.py
git commit -m "feat(exporters): implement executive FinOps opportunities report generator"
```

---

### Task 4: CLI Integration & End-to-End Verification

**Files:**
- Modify: `src/main.py:1-90`
- Modify: `tests/test_e2e.py`

**Interfaces:**
- Consumes: `analyze_finops_opportunities` de `src/finops_analyzer.py`, `export_finops_opportunities_markdown` de `src/exporters/finops_report.py`.
- Produces: Execução automática na CLI e arquivo `output/relatorio_oportunidades_finops_<conta>.md`.

- [ ] **Step 1: Atualizar teste de ponta a ponta em `tests/test_e2e.py`**

Adicionar asserção em `tests/test_e2e.py` para garantir que o terceiro entregável seja gerado:

```python
def test_full_pipeline_execution(tmp_path):
    # ... código existente de setup ...
    # Asserção existente para .xlsx e relatorio_<conta>.md
    # Nova asserção:
    finops_opp_file = tmp_path / "relatorio_oportunidades_finops_testaccount.md"
    assert finops_opp_file.exists()
    opp_content = finops_opp_file.read_text(encoding="utf-8")
    assert "Relatório Executivo de Oportunidades FinOps" in opp_content
    assert "Scorecard Executivo & Impacto Financeiro" in opp_content
    assert "Playbooks Práticos de Investigação" in opp_content
```

- [ ] **Step 2: Executar o teste e verificar a falha**

Run: `python -m pytest tests/test_e2e.py -v`  
Expected: FAIL com `AssertionError: assert False where False = Path(...).exists()`

- [ ] **Step 3: Atualizar `src/main.py` para incluir o novo módulo e entregável**

Em `src/main.py`:
- Importar `analyze_finops_opportunities` de `src.finops_analyzer`.
- Importar `export_finops_opportunities_markdown` de `src.exporters.finops_report`.
- Dentro de `run_pipeline`:
  ```python
  # 5. Análise Estratégica de Oportunidades FinOps
  finops_analysis = analyze_finops_opportunities(report_data)
  finops_opp_md_filename = f"relatorio_oportunidades_finops_{account_name}.md"
  finops_opp_md_path = os.path.join(output_dir, finops_opp_md_filename)
  export_finops_opportunities_markdown(finops_analysis, finops_opp_md_path)
  print(f"[OK] Relatório executivo de oportunidades FinOps gerado: {finops_opp_md_path}")
  ```

- [ ] **Step 4: Executar a suíte de testes completa**

Run: `python -m pytest -v`  
Expected: PASS com 100% dos testes passando.

- [ ] **Step 5: Executar o pipeline real contra os dados de `contas/multicanais-dev`**

Run: `python -m src.main --input-dir contas/multicanais-dev --output-dir output`  
Expected: Sucesso na geração dos 3 arquivos em `output/`:
- `output/inventario_multicanais-dev.xlsx`
- `output/relatorio_multicanais-dev.md`
- `output/relatorio_oportunidades_finops_multicanais-dev.md`

- [ ] **Step 6: Commit**

```bash
git add src/main.py tests/test_e2e.py
git commit -m "feat(main): integrate executive FinOps opportunities report into CLI pipeline"
```

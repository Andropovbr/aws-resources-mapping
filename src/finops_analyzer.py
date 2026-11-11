import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from src.models import (
    ResourceRecord,
    InventoryReportData,
    PlaybookGuide,
    FinOpsOpportunity,
    FinOpsAnalysisResult
)
from src.finops import is_test_resource

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
    rds_instances = [
        r for r in resources
        if r.service.lower() == "rds"
        and (
            "dbinstance" in (r.resource_type or "").lower()
            or (r.resource_type or "").lower() == "rds:db"
            or "dbinstance" in (r.cfn_resource_type or "").lower()
        )
    ]
    eips = [r for r in resources if "eip" in r.resource_type.lower() or "elastic-ip" in r.resource_type.lower()]
    snapshots = [r for r in resources if "snapshot" in r.resource_type.lower()]
    test_resources = [
        r for r in resources
        if is_test_resource(r.identifier)
        and r.macro_domain != "Governança"
    ]

    # --- PILAR A: Padrões de Consumo & Anomalias ---
    # A1: Dispersão Regional
    main_regions = {"ca-central-1", "sa-east-1"}
    foreign_regions = {reg: count for reg, count in report_data.regions.items() if reg not in main_regions and reg != "global"}
    total_foreign = sum(foreign_regions.values())
    foreign_actionable_resources = [
        r for r in resources
        if r.region not in main_regions and r.region != "global" and r.macro_domain != "Governança"
    ]
    if total_foreign > 0:
        foreign_actionable_count = len(foreign_actionable_resources)
        estimated_savings = foreign_actionable_count * 1.5 if foreign_actionable_count > 0 else 0.0
        consumption_opps.append(FinOpsOpportunity(
            pillar="Padrões de Consumo",
            title="Dispersão de Recursos em Regiões Secundárias",
            description=(
                f"Foram identificados {total_foreign} recursos distribuídos em {len(foreign_regions)} regiões "
                f"secundárias fora do núcleo do projeto ({', '.join(sorted(foreign_regions.keys())[:5])}...), "
                f"sendo {foreign_actionable_count} recursos fora de governança/baseline corporativo. "
                f"Em ambiente de desenvolvimento, isso indica testes residuais ou criação não intencional."
            ),
            evidence_status="[NECESSITA ANÁLISE]",
            effort_level="Baixo (Quick Win)",
            impact_level="Médio",
            estimated_monthly_savings_usd=estimated_savings if estimated_savings > 0 else None,
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
    primary_region = "ca-central-1" if "ca-central-1" in report_data.regions else ("sa-east-1" if "sa-east-1" in report_data.regions else "us-east-1")

    now = datetime.now(timezone.utc)
    date_end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_start_14d = (now - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00Z")
    date_start_30d = (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    date_snapshot_filter = (now - timedelta(days=60)).strftime("%Y-%m-%d")

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
            f"--start-time {date_start_14d} --end-time {date_end} --period 86400 --statistics Average Maximum"
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
            f"--start-time {date_start_30d} --end-time {date_end} --period 86400 --statistics Sum"
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
            f"--start-time {date_start_14d} --end-time {date_end} --period 3600 --statistics Maximum"
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
            f"--query 'Snapshots[?StartTime<=`{date_snapshot_filter}`].[SnapshotId,VolumeId,StartTime]' --output table"
        ),
        decision_criteria="Snapshots de instâncias já deletadas ou rotinas de teste finalizadas.",
        recommended_action="Excluir snapshots legados e configurar regra de ciclo de vida automática no AWS Backup."
    ))

    # Playbook 5: Auditoria e Limpeza de Recursos em Regiões Secundárias
    if total_foreign > 0:
        sample_foreign_region = sorted(foreign_regions.keys())[0]
        playbooks.append(PlaybookGuide(
            playbook_id="pb-cross-region-cleanup",
            title="Playbook 5: Auditoria de Recursos em Regiões Secundárias",
            target_metric="Recursos provisionados em regiões fora do escopo principal do projeto",
            target_resources=sorted(foreign_regions.keys()),
            console_path="AWS Console > AWS Tag Editor / Resource Groups (All Regions)",
            aws_cli_command=(
                f"# Listar recursos com tags ou stacks ativas na região secundária ({sample_foreign_region}):\n"
                f"aws resourcegroupstaggingapi get-resources --region {sample_foreign_region} --query 'ResourceTagMappingList[*].ResourceARN' --output table"
            ),
            decision_criteria="Se os recursos forem resíduos de testes antigos ou sem tráfego.",
            recommended_action="Encerrar recursos órfãos na região secundária e aplicar SCP via AWS Organizations bloqueando regiões não autorizadas."
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
        playbooks=playbooks,
        account_name=report_data.account_name,
        account_display=report_data.account_display,
    )

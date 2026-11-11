from typing import Dict, List, Set
from src.models import (
    InventoryReportData,
    ResourceRecord,
    OrphanCandidate,
    OrphanPlaybookGuide,
    OrphanAnalysisResult,
)

CATEGORIES = [
    "Armazenamento",
    "Rede & Conectividade",
    "Balanceamento de Carga",
    "Cache & Dados In-Memory",
    "Segurança, Logs & Certificados",
]

PLAYBOOK_DEFINITIONS = {
    "pb-orphan-ebs-volumes": {
        "title": "Playbook 1: Auditoria e Descarte de Volumes EBS Desanexados",
        "category": "Armazenamento",
        "inspection_console_path": "EC2 > Elastic Block Store > Volumes (Filtrar por Status: Available)",
        "inspection_cli_command": "aws ec2 describe-volumes --region <region> --filters Name=status,Values=available --query 'Volumes[*].{VolumeId:VolumeId,Size:Size,CreateTime:CreateTime}' --output table",
        "decision_criteria": "Validar se o status do volume está 'available' (desanexado) e se os dados residuais não são mais necessários para restauração.",
        "safe_cleanup_cli_command": "aws ec2 delete-volume --region <region> --volume-id <vol-id>",
        "safety_recommendation": "Criar um snapshot manual do volume (aws ec2 create-snapshot) antes de excluí-lo permanentemente.",
    },
    "pb-orphan-snapshots": {
        "title": "Playbook 2: Auditoria e Descarte de Snapshots Residuais (EBS e RDS)",
        "category": "Armazenamento",
        "inspection_console_path": "EC2 > Snapshots / RDS > Snapshots",
        "inspection_cli_command": (
            "# Para Snapshots EBS (EC2):\n"
            "aws ec2 describe-snapshots --region <region> --owner-ids self --query 'Snapshots[*].{SnapshotId:SnapshotId,VolumeId:VolumeId,StartTime:StartTime}' --output table\n\n"
            "# Para Snapshots RDS:\n"
            "aws rds describe-db-snapshots --region <region> --snapshot-type manual --query 'DBSnapshots[*].{DBSnapshotIdentifier:DBSnapshotIdentifier,DBInstanceIdentifier:DBInstanceIdentifier,SnapshotCreateTime:SnapshotCreateTime}' --output table"
        ),
        "decision_criteria": "Validar se o snapshot manual é anterior à política de retenção da organização e se a instância/volume de origem já foi extinta.",
        "safe_cleanup_cli_command": (
            "# Para Snapshots EBS (EC2):\n"
            "aws ec2 delete-snapshot --region <region> --snapshot-id <snapshot-id>\n\n"
            "# Para Snapshots RDS:\n"
            "aws rds delete-db-snapshot --region <region> --db-snapshot-identifier <snapshot-id>"
        ),
        "safety_recommendation": "Confirmar com os mantenedores da aplicação se a imagem/snapshot não é requisito de conformidade ou disaster recovery.",
    },
    "pb-orphan-elastic-ips": {
        "title": "Playbook 3: Auditoria e Liberação de Elastic IPs Não Associados",
        "category": "Rede & Conectividade",
        "inspection_console_path": "EC2 > Network & Security > Elastic IPs",
        "inspection_cli_command": "aws ec2 describe-addresses --region <region> --query 'Addresses[?NetworkInterfaceId==null].{AllocationId:AllocationId,PublicIp:PublicIp}' --output table",
        "decision_criteria": "Confirmar se o Elastic IP não está associado a nenhuma interface de rede ativa (NetworkInterfaceId nulo).",
        "safe_cleanup_cli_command": "aws ec2 release-address --region <region> --allocation-id <alloc-id>",
        "safety_recommendation": "Verificar se o endereço IP público não consta em zonas DNS externas antes da liberação.",
    },
    "pb-orphan-enis": {
        "title": "Playbook 4: Auditoria e Exclusão de Interfaces de Rede (ENIs) Desanexadas",
        "category": "Rede & Conectividade",
        "inspection_console_path": "EC2 > Network Interfaces (Filtrar por Status: Available)",
        "inspection_cli_command": "aws ec2 describe-network-interfaces --region <region> --filters Name=status,Values=available --query 'NetworkInterfaces[*].{NetworkInterfaceId:NetworkInterfaceId,VpcId:VpcId,Description:Description}' --output table",
        "decision_criteria": "Validar se o status de anexo da interface é 'available' e se não pertence a instâncias Lambda em VPC ou serviços em transição.",
        "safe_cleanup_cli_command": "aws ec2 delete-network-interface --region <region> --network-interface-id <eni-id>",
        "safety_recommendation": "Verificar se a interface não é resquício temporário de VPC Endpoint ou NAT Gateway recém-alterado.",
    },
    "pb-orphan-security-groups": {
        "title": "Playbook 5: Auditoria e Limpeza de Security Groups Não Utilizados",
        "category": "Rede & Conectividade",
        "inspection_console_path": "VPC > Security Groups / EC2 > Security Groups",
        "inspection_cli_command": "aws ec2 describe-security-groups --region <region> --query 'SecurityGroups[?GroupName!=`default`].{GroupId:GroupId,GroupName:GroupName}' --output table",
        "decision_criteria": "Certificar-se de que não existem ENIs ativas vinculadas ao grupo de segurança e que o grupo não é o 'default'.",
        "safe_cleanup_cli_command": "aws ec2 delete-security-group --region <region> --group-id <sg-id>",
        "safety_recommendation": "Exportar e documentar as regras de entrada/saída do Security Group antes da remoção definitiva.",
    },
    "pb-orphan-albs-targetgroups": {
        "title": "Playbook 6: Auditoria e Desativação de ALBs e Target Groups Ociosos",
        "category": "Balanceamento de Carga",
        "inspection_console_path": "EC2 > Load Balancing > Load Balancers / Target Groups",
        "inspection_cli_command": "aws elbv2 describe-target-health --region <region> --target-group-arn <tg-arn>",
        "decision_criteria": "Confirmar métricas de RequestCount zeradas no CloudWatch nos últimos 14 dias ou ausência de instâncias saudáveis no Target Group.",
        "safe_cleanup_cli_command": "aws elbv2 delete-load-balancer --region <region> --load-balancer-arn <alb-arn> && aws elbv2 delete-target-group --region <region> --target-group-arn <tg-arn>",
        "safety_recommendation": "Apontar tráfego DNS de contingência e remover listeners antes de deletar o Load Balancer.",
    },
    "pb-orphan-cache-users": {
        "title": "Playbook 7: Auditoria e Remoção de Usuários e ACLs de Cache Órfãos",
        "category": "Cache & Dados In-Memory",
        "inspection_console_path": "Amazon MemoryDB / ElastiCache > Users / Access Control Lists",
        "inspection_cli_command": (
            "# Para MemoryDB:\n"
            "aws memorydb describe-clusters --region <region> && aws memorydb describe-users --region <region>\n\n"
            "# Para ElastiCache:\n"
            "aws elasticache describe-cache-clusters --region <region> && aws elasticache describe-users --region <region>"
        ),
        "decision_criteria": "Confirmar ausência de clusters ativos na região ou desvinculação completa de ACLs e credenciais.",
        "safe_cleanup_cli_command": (
            "# Para MemoryDB:\n"
            "aws memorydb delete-user --region <region> --user-name <user-name>\n"
            "aws memorydb delete-acl --region <region> --acl-name <acl-name>\n\n"
            "# Para ElastiCache:\n"
            "aws elasticache delete-user --region <region> --user-id <user-id>"
        ),
        "safety_recommendation": "Fazer backup prévio das ACLs e mapeamento de usuários antes de remover credenciais residuais.",
    },
    "pb-orphan-acm-certs": {
        "title": "Playbook 8: Auditoria de Certificados ACM Sem Vínculo Ativo",
        "category": "Segurança, Logs & Certificados",
        "inspection_console_path": "AWS Certificate Manager > Certificates",
        "inspection_cli_command": "aws acm describe-certificate --region <region> --certificate-arn <cert-arn> --query 'Certificate.InUseBy' --output table",
        "decision_criteria": "Validar se a lista 'InUseBy' do certificado está vazia e nenhuma distribuição CloudFront ou ALB depende dele.",
        "safe_cleanup_cli_command": "aws acm delete-certificate --region <region> --certificate-arn <cert-arn>",
        "safety_recommendation": "Garantir que nenhum registro CNAME externo dependa da validação do certificado antes do descarte.",
    },
    "pb-orphan-cloudwatch-logs": {
        "title": "Playbook 9: Auditoria e Configuração de Retenção de Log Groups",
        "category": "Segurança, Logs & Certificados",
        "inspection_console_path": "CloudWatch > Logs > Log groups",
        "inspection_cli_command": "aws logs describe-log-groups --region <region> --query 'logGroups[?retentionInDays==null].{logGroupName:logGroupName,storedBytes:storedBytes}' --output table",
        "decision_criteria": "Verificar se o recurso emissor dos logs foi deletado ou configurar retenção automática (ex.: 30 dias).",
        "safe_cleanup_cli_command": "aws logs delete-log-group --region <region> --log-group-name <log-group-name>",
        "safety_recommendation": "Exportar dados históricos relevantes para um bucket S3 com arquivamento no Glacier se houver exigência de auditoria.",
    },
}


class CategoryBreakdownDict(dict):
    """Dictionary supporting category name aliases like 'Rede' for 'Rede & Conectividade'."""

    def __getitem__(self, key: str):
        if key == "Rede" and "Rede" not in self and "Rede & Conectividade" in self:
            return self["Rede & Conectividade"]
        if key == "Segurança" and "Segurança" not in self and "Segurança, Logs & Certificados" in self:
            return self["Segurança, Logs & Certificados"]
        if key == "Balanceamento" and "Balanceamento" not in self and "Balanceamento de Carga" in self:
            return self["Balanceamento de Carga"]
        if key == "Cache" and "Cache" not in self and "Cache & Dados In-Memory" in self:
            return self["Cache & Dados In-Memory"]
        return super().__getitem__(key)


def _find_active_cache_regions(resources: List[ResourceRecord]) -> Set[str]:
    """Identifies regions with active ElastiCache or MemoryDB clusters."""
    cluster_regions = set()
    for r in resources:
        service_lower = (r.service or "").lower()
        type_lower = (r.resource_type or "").lower()
        cfn_lower = (r.cfn_resource_type or "").lower()
        combined = f"{service_lower} {type_lower} {cfn_lower}"

        if ("elasticache" in combined or "memorydb" in combined) and "cluster" in combined:
            cluster_regions.add(r.region)
    return cluster_regions


def analyze_orphaned_resources(report_data: InventoryReportData) -> OrphanAnalysisResult:
    """
    Analyzes an inventory of AWS resources across 5 key domains to identify
    potential or confirmed orphan resources, calculating estimated waste and
    providing remediation playbooks.
    """
    categories_breakdown = CategoryBreakdownDict({cat: [] for cat in CATEGORIES})
    all_candidates: List[OrphanCandidate] = []
    playbook_target_resources: Dict[str, List[str]] = {pb_id: [] for pb_id in PLAYBOOK_DEFINITIONS}

    active_cache_regions = _find_active_cache_regions(report_data.all_resources)

    for r in report_data.all_resources:
        if (r.macro_domain or "").lower() in ("governança", "governanca"):
            continue

        service_lower = (r.service or "").lower()
        type_lower = (r.resource_type or "").lower()
        cfn_lower = (r.cfn_resource_type or "").lower()
        ident_lower = (r.identifier or "").lower()
        name_lower = (r.resource_name or "").lower()

        # -------------------------------------------------------------
        # 1. Armazenamento (Storage)
        # -------------------------------------------------------------
        if type_lower == "ec2:volume" or cfn_lower == "aws::ec2::volume":
            cand = OrphanCandidate(
                category="Armazenamento",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status="[CANDIDATO A ÓRFÃO]",
                confidence_rationale="Volume EBS provisionado; o inventário estático não detalha anexo ativo (in-use vs available). Validar se está desacoplado.",
                estimated_monthly_waste_usd=8.00,
                playbook_id="pb-orphan-ebs-volumes",
            )
            categories_breakdown["Armazenamento"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-ebs-volumes"].append(r.identifier)
            continue

        if type_lower == "ec2:snapshot" or cfn_lower == "aws::ec2::snapshot":
            cand = OrphanCandidate(
                category="Armazenamento",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status="[CANDIDATO A ÓRFÃO]",
                confidence_rationale="Snapshot EBS manual retido na conta sem ciclo de vida automático configurado.",
                estimated_monthly_waste_usd=2.50,
                playbook_id="pb-orphan-snapshots",
            )
            categories_breakdown["Armazenamento"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-snapshots"].append(r.identifier)
            continue

        if (
            type_lower in ("rds:snapshot", "rds:cluster-snapshot")
            or cfn_lower in ("aws::rds::dbsnapshot", "aws::rds::dbclustersnapshot")
            or (service_lower == "rds" and "snapshot" in type_lower)
        ):
            cand = OrphanCandidate(
                category="Armazenamento",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status="[CANDIDATO A ÓRFÃO]",
                confidence_rationale="Snapshot manual de banco RDS retido além do ciclo de backup automatizado.",
                estimated_monthly_waste_usd=5.00,
                playbook_id="pb-orphan-snapshots",
            )
            categories_breakdown["Armazenamento"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-snapshots"].append(r.identifier)
            continue

        # -------------------------------------------------------------
        # 2. Rede & Conectividade (Networking)
        # -------------------------------------------------------------
        if (
            type_lower == "ec2:elastic-ip"
            or "elastic-ip" in type_lower
            or cfn_lower in ("aws::ec2::eip", "aws::ec2::elasticip")
            or (service_lower == "ec2" and "eip" in type_lower)
        ):
            cand = OrphanCandidate(
                category="Rede & Conectividade",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status="[CANDIDATO A ÓRFÃO]",
                confidence_rationale="Elastic IP alocado. EIPs desassociados de instâncias ativas na AWS sofrem cobrança contínua ($0.005/h).",
                estimated_monthly_waste_usd=3.65,
                playbook_id="pb-orphan-elastic-ips",
            )
            categories_breakdown["Rede & Conectividade"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-elastic-ips"].append(r.identifier)
            continue

        if (
            type_lower in ("ec2:network-interface", "eni")
            or cfn_lower == "aws::ec2::networkinterface"
            or (service_lower == "ec2" and "network-interface" in type_lower)
        ):
            cand = OrphanCandidate(
                category="Rede & Conectividade",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status="[CANDIDATO A ÓRFÃO]",
                confidence_rationale="Interface de rede ENI identificada; validar se o status de anexo está 'available' (solta) para evitar IP leaks.",
                estimated_monthly_waste_usd=0.00,
                playbook_id="pb-orphan-enis",
            )
            categories_breakdown["Rede & Conectividade"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-enis"].append(r.identifier)
            continue

        if (
            type_lower == "ec2:security-group"
            or cfn_lower == "aws::ec2::securitygroup"
            or (service_lower == "ec2" and type_lower == "security-group")
        ) and not (type_lower.endswith("-rule") or "rule" in type_lower):
            # Ignore default security groups
            if ident_lower == "default" or name_lower == "default":
                continue

            cand = OrphanCandidate(
                category="Rede & Conectividade",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status="[CANDIDATO A ÓRFÃO]",
                confidence_rationale="Security Group manual criado; validar se possui interfaces de rede ativas associadas para evitar sprawl.",
                estimated_monthly_waste_usd=0.00,
                playbook_id="pb-orphan-security-groups",
            )
            categories_breakdown["Rede & Conectividade"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-security-groups"].append(r.identifier)
            continue

        # -------------------------------------------------------------
        # 3. Balanceamento de Carga (Load Balancing)
        # -------------------------------------------------------------
        if (
            type_lower in ("elasticloadbalancing:loadbalancer", "elasticloadbalancing:loadbalancer/app", "elasticloadbalancing:loadbalancer/net")
            or cfn_lower in ("aws::elasticloadbalancingv2::loadbalancer", "aws::elasticloadbalancing::loadbalancer")
            or (service_lower == "elasticloadbalancing" and ("loadbalancer" in type_lower or "loadbalancer" in cfn_lower))
        ):
            cand = OrphanCandidate(
                category="Balanceamento de Carga",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status="[CANDIDATO A ÓRFÃO]",
                confidence_rationale="Application Load Balancer ativo em ambiente dev com custo fixo mensal; auditar volume de requisições.",
                estimated_monthly_waste_usd=22.50,
                playbook_id="pb-orphan-albs-targetgroups",
            )
            categories_breakdown["Balanceamento de Carga"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-albs-targetgroups"].append(r.identifier)
            continue

        if (
            type_lower == "elasticloadbalancing:targetgroup"
            or cfn_lower == "aws::elasticloadbalancingv2::targetgroup"
            or (service_lower == "elasticloadbalancing" and "targetgroup" in (type_lower + cfn_lower))
        ):
            cand = OrphanCandidate(
                category="Balanceamento de Carga",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status="[CANDIDATO A ÓRFÃO]",
                confidence_rationale="Target Group registrado; validar se possui instâncias saudáveis ou se está desvinculado de listeners.",
                estimated_monthly_waste_usd=0.00,
                playbook_id="pb-orphan-albs-targetgroups",
            )
            categories_breakdown["Balanceamento de Carga"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-albs-targetgroups"].append(r.identifier)
            continue

        # -------------------------------------------------------------
        # 4. Cache & Dados In-Memory
        # -------------------------------------------------------------
        if (
            type_lower in ("elasticache:user", "memorydb:user", "memorydb:acl", "memorydb:parametergroup")
            or cfn_lower in ("aws::elasticache::user", "aws::memorydb::user", "aws::memorydb::acl", "aws::memorydb::parametergroup")
        ):
            if ident_lower == "default" or ident_lower.startswith("default.") or name_lower == "default":
                continue

            region_has_cluster = r.region in active_cache_regions
            if not region_has_cluster:
                status = "[CONFIRMADO ÓRFÃO]"
                rationale = "Credencial ou configuração residual de banco em memória em região sem clusters ativos."
            else:
                status = "[CANDIDATO A ÓRFÃO]"
                rationale = "Credencial ou configuração residual de banco em memória; auditar associação aos clusters ativos."

            cand = OrphanCandidate(
                category="Cache & Dados In-Memory",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status=status,
                confidence_rationale=rationale,
                estimated_monthly_waste_usd=0.00,
                playbook_id="pb-orphan-cache-users",
            )
            categories_breakdown["Cache & Dados In-Memory"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-cache-users"].append(r.identifier)
            continue

        # -------------------------------------------------------------
        # 5. Segurança, Logs & Certificados
        # -------------------------------------------------------------
        if type_lower == "acm:certificate" or cfn_lower == "aws::certificatemanager::certificate":
            cand = OrphanCandidate(
                category="Segurança, Logs & Certificados",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status="[CANDIDATO A ÓRFÃO]",
                confidence_rationale="Certificado digital emitido; validar associação ativa a Load Balancers ou distribuições CloudFront.",
                estimated_monthly_waste_usd=0.00,
                playbook_id="pb-orphan-acm-certs",
            )
            categories_breakdown["Segurança, Logs & Certificados"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-acm-certs"].append(r.identifier)
            continue

        if (
            type_lower == "logs:log-group"
            or cfn_lower == "aws::logs::loggroup"
            or (service_lower == "logs" and "log-group" in type_lower)
        ):
            cand = OrphanCandidate(
                category="Segurança, Logs & Certificados",
                resource_type=r.resource_type,
                resource_identifier=r.identifier,
                resource_name=r.resource_name,
                region=r.region,
                status="[CANDIDATO A ÓRFÃO]",
                confidence_rationale="CloudWatch Log Group sem expiração definida ou de funções Lambda deletadas acumulando custo de retenção.",
                estimated_monthly_waste_usd=1.50,
                playbook_id="pb-orphan-cloudwatch-logs",
            )
            categories_breakdown["Segurança, Logs & Certificados"].append(cand)
            all_candidates.append(cand)
            playbook_target_resources["pb-orphan-cloudwatch-logs"].append(r.identifier)
            continue

    # -------------------------------------------------------------
    # Build Playbook Guides for Referenced Playbooks
    # -------------------------------------------------------------
    playbooks: List[OrphanPlaybookGuide] = []
    for pb_id, targets in playbook_target_resources.items():
        if targets:
            meta = PLAYBOOK_DEFINITIONS[pb_id]
            guide = OrphanPlaybookGuide(
                playbook_id=pb_id,
                title=meta["title"],
                category=meta["category"],
                target_resources=list(dict.fromkeys(targets)),
                inspection_console_path=meta["inspection_console_path"],
                inspection_cli_command=meta["inspection_cli_command"],
                decision_criteria=meta["decision_criteria"],
                safe_cleanup_cli_command=meta["safe_cleanup_cli_command"],
                safety_recommendation=meta["safety_recommendation"],
            )
            playbooks.append(guide)

    # -------------------------------------------------------------
    # Totals Calculation
    # -------------------------------------------------------------
    confirmed_count = sum(1 for c in all_candidates if c.status == "[CONFIRMADO ÓRFÃO]")
    potential_count = sum(1 for c in all_candidates if c.status == "[CANDIDATO A ÓRFÃO]")
    total_waste = round(sum(c.estimated_monthly_waste_usd for c in all_candidates), 2)

    return OrphanAnalysisResult(
        account_id=report_data.account_id,
        total_candidates=len(all_candidates),
        confirmed_orphans_count=confirmed_count,
        potential_orphans_count=potential_count,
        total_estimated_monthly_waste_usd=total_waste,
        categories_breakdown=categories_breakdown,
        playbooks=playbooks,
        account_name=report_data.account_name,
        account_display=report_data.account_display,
    )

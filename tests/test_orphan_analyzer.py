import pytest
from src.models import ResourceRecord, InventoryReportData
from src.orphan_analyzer import analyze_orphaned_resources


def _make_resource(
    ident: str,
    r_type: str,
    service: str,
    region: str = "ca-central-1",
    name: str = "-",
    cfn_type: str = "-",
    domain: str = "Aplicação",
) -> ResourceRecord:
    return ResourceRecord(
        identifier=ident,
        arn=f"arn:aws:{service}:{region}:123456789012:{ident}",
        resource_type=r_type,
        region=region,
        aws_account="123456789012",
        application_raw="-",
        cfn_resource_type=cfn_type,
        last_reported_at="2026-10-10",
        service=service,
        tags="0",
        resource_name=name,
        macro_domain=domain,
    )


def _make_report_data(resources) -> InventoryReportData:
    regions = {}
    services = {}
    for r in resources:
        regions[r.region] = regions.get(r.region, 0) + 1
        services[r.service] = services.get(r.service, 0) + 1
    return InventoryReportData(
        account_id="123456789012",
        total_resources=len(resources),
        unique_arns=len(resources),
        regions=regions,
        services=services,
        macro_domains={"Aplicação": len(resources)},
        finops_summary={},
        clusters=[],
        all_resources=resources,
    )


def test_orphan_analyzer_storage_domain():
    vol = _make_resource("vol-0123456789abcdef0", "ec2:volume", "ec2", name="disk-1")
    ec2_snap = _make_resource("snap-0123456789abcdef0", "ec2:snapshot", "ec2", name="snap-ec2")
    rds_snap = _make_resource("rds-snap-manual-1", "rds:snapshot", "rds", name="snap-rds")

    data = _make_report_data([vol, ec2_snap, rds_snap])
    result = analyze_orphaned_resources(data)

    assert result.total_candidates == 3
    assert result.total_estimated_monthly_waste_usd == pytest.approx(8.00 + 2.50 + 5.00, 0.01)

    storage = result.categories_breakdown["Armazenamento"]
    assert len(storage) == 3

    # Check EBS volume
    cand_vol = next(c for c in storage if c.resource_identifier == "vol-0123456789abcdef0")
    assert cand_vol.status == "[CANDIDATO A ÓRFÃO]"
    assert cand_vol.estimated_monthly_waste_usd == 8.00
    assert cand_vol.playbook_id == "pb-orphan-ebs-volumes"
    assert "Volume EBS provisionado" in cand_vol.confidence_rationale

    # Check EC2 snapshot
    cand_ec2_snap = next(c for c in storage if c.resource_identifier == "snap-0123456789abcdef0")
    assert cand_ec2_snap.status == "[CANDIDATO A ÓRFÃO]"
    assert cand_ec2_snap.estimated_monthly_waste_usd == 2.50
    assert cand_ec2_snap.playbook_id == "pb-orphan-snapshots"

    # Check RDS snapshot
    cand_rds_snap = next(c for c in storage if c.resource_identifier == "rds-snap-manual-1")
    assert cand_rds_snap.status == "[CANDIDATO A ÓRFÃO]"
    assert cand_rds_snap.estimated_monthly_waste_usd == 5.00
    assert cand_rds_snap.playbook_id == "pb-orphan-snapshots"

    # Playbooks check
    playbook_ids = {pb.playbook_id for pb in result.playbooks}
    assert "pb-orphan-ebs-volumes" in playbook_ids
    assert "pb-orphan-snapshots" in playbook_ids

    pb_snap = next(pb for pb in result.playbooks if pb.playbook_id == "pb-orphan-snapshots")
    assert "snap-0123456789abcdef0" in pb_snap.target_resources
    assert "rds-snap-manual-1" in pb_snap.target_resources


def test_orphan_analyzer_networking_domain():
    eip = _make_resource("18.230.1.2", "ec2:elastic-ip", "ec2", name="my-eip")
    eni = _make_resource("eni-0123456789abcdef0", "ec2:network-interface", "ec2", name="my-eni")
    sg_custom = _make_resource("sg-0123456789abcdef0", "ec2:security-group", "ec2", name="custom-sg")
    sg_default_id = _make_resource("default", "ec2:security-group", "ec2", name="default")
    sg_default_name = _make_resource("sg-default-id", "ec2:security-group", "ec2", name="default")

    data = _make_report_data([eip, eni, sg_custom, sg_default_id, sg_default_name])
    result = analyze_orphaned_resources(data)

    # sg_default_id and sg_default_name should be ignored
    networking = result.categories_breakdown["Rede & Conectividade"]
    assert len(networking) == 3
    # Check alias compatibility
    assert len(result.categories_breakdown["Rede"]) == 3

    cand_eip = next(c for c in networking if c.resource_identifier == "18.230.1.2")
    assert cand_eip.status == "[CANDIDATO A ÓRFÃO]"
    assert cand_eip.estimated_monthly_waste_usd == 3.65
    assert cand_eip.playbook_id == "pb-orphan-elastic-ips"

    cand_eni = next(c for c in networking if c.resource_identifier == "eni-0123456789abcdef0")
    assert cand_eni.status == "[CANDIDATO A ÓRFÃO]"
    assert cand_eni.estimated_monthly_waste_usd == 0.00
    assert cand_eni.playbook_id == "pb-orphan-enis"

    cand_sg = next(c for c in networking if c.resource_identifier == "sg-0123456789abcdef0")
    assert cand_sg.status == "[CANDIDATO A ÓRFÃO]"
    assert cand_sg.estimated_monthly_waste_usd == 0.00
    assert cand_sg.playbook_id == "pb-orphan-security-groups"

    assert result.total_estimated_monthly_waste_usd == pytest.approx(3.65, 0.01)


def test_orphan_analyzer_load_balancing_domain():
    alb = _make_resource(
        "app/my-alb/12345",
        "elasticloadbalancing:loadbalancer/app",
        "elasticloadbalancing",
        name="my-alb",
    )
    tg = _make_resource(
        "targetgroup/my-tg/67890",
        "elasticloadbalancing:targetgroup",
        "elasticloadbalancing",
        name="my-tg",
    )

    data = _make_report_data([alb, tg])
    result = analyze_orphaned_resources(data)

    lb_candidates = result.categories_breakdown["Balanceamento de Carga"]
    assert len(lb_candidates) == 2

    cand_alb = next(c for c in lb_candidates if c.resource_identifier == "app/my-alb/12345")
    assert cand_alb.status == "[CANDIDATO A ÓRFÃO]"
    assert cand_alb.estimated_monthly_waste_usd == 22.50
    assert cand_alb.playbook_id == "pb-orphan-albs-targetgroups"

    cand_tg = next(c for c in lb_candidates if c.resource_identifier == "targetgroup/my-tg/67890")
    assert cand_tg.status == "[CANDIDATO A ÓRFÃO]"
    assert cand_tg.estimated_monthly_waste_usd == 0.00
    assert cand_tg.playbook_id == "pb-orphan-albs-targetgroups"

    assert result.total_estimated_monthly_waste_usd == pytest.approx(22.50, 0.01)
    pb_alb = next(pb for pb in result.playbooks if pb.playbook_id == "pb-orphan-albs-targetgroups")
    assert "app/my-alb/12345" in pb_alb.target_resources
    assert "targetgroup/my-tg/67890" in pb_alb.target_resources


def test_orphan_analyzer_cache_domain_no_clusters():
    # In sa-east-1, no clusters exist
    user_mem = _make_resource("mem-user-1", "memorydb:user", "memorydb", region="sa-east-1")
    acl_mem = _make_resource("mem-acl-1", "memorydb:acl", "memorydb", region="sa-east-1")
    param_mem = _make_resource("mem-param-1", "memorydb:parametergroup", "memorydb", region="sa-east-1")
    user_ec = _make_resource("ec-user-1", "elasticache:user", "elasticache", region="sa-east-1")

    data = _make_report_data([user_mem, acl_mem, param_mem, user_ec])
    result = analyze_orphaned_resources(data)

    cache_candidates = result.categories_breakdown["Cache & Dados In-Memory"]
    assert len(cache_candidates) == 4

    for cand in cache_candidates:
        assert cand.status == "[CONFIRMADO ÓRFÃO]"
        assert cand.estimated_monthly_waste_usd == 0.00
        assert cand.playbook_id == "pb-orphan-cache-users"
        assert "região sem clusters ativos" in cand.confidence_rationale

    assert result.confirmed_orphans_count == 4
    assert result.potential_orphans_count == 0


def test_orphan_analyzer_cache_domain_with_active_cluster():
    # In us-east-1, there is an active cluster
    cluster = _make_resource("my-cache-cluster", "elasticache:cluster", "elasticache", region="us-east-1")
    user_ec = _make_resource("ec-user-2", "elasticache:user", "elasticache", region="us-east-1")

    data = _make_report_data([cluster, user_ec])
    result = analyze_orphaned_resources(data)

    cache_candidates = result.categories_breakdown["Cache & Dados In-Memory"]
    assert len(cache_candidates) == 1
    assert cache_candidates[0].status == "[CANDIDATO A ÓRFÃO]"
    assert result.confirmed_orphans_count == 0
    assert result.potential_orphans_count == 1


def test_orphan_analyzer_security_and_logs_domain():
    cert = _make_resource("cert-12345", "acm:certificate", "acm", name="api.example.com")
    log_group = _make_resource("/aws/lambda/old-function", "logs:log-group", "logs", name="/aws/lambda/old-function")

    data = _make_report_data([cert, log_group])
    result = analyze_orphaned_resources(data)

    sec_candidates = result.categories_breakdown["Segurança, Logs & Certificados"]
    assert len(sec_candidates) == 2

    cand_cert = next(c for c in sec_candidates if c.resource_identifier == "cert-12345")
    assert cand_cert.status == "[CANDIDATO A ÓRFÃO]"
    assert cand_cert.estimated_monthly_waste_usd == 0.00
    assert cand_cert.playbook_id == "pb-orphan-acm-certs"

    cand_log = next(c for c in sec_candidates if c.resource_identifier == "/aws/lambda/old-function")
    assert cand_log.status == "[CANDIDATO A ÓRFÃO]"
    assert cand_log.estimated_monthly_waste_usd == 1.50
    assert cand_log.playbook_id == "pb-orphan-cloudwatch-logs"

    assert result.total_estimated_monthly_waste_usd == pytest.approx(1.50, 0.01)


def test_orphan_analyzer_empty_inventory():
    data = _make_report_data([])
    result = analyze_orphaned_resources(data)

    assert result.total_candidates == 0
    assert result.confirmed_orphans_count == 0
    assert result.potential_orphans_count == 0
    assert result.total_estimated_monthly_waste_usd == 0.0
    assert result.playbooks == []
    for cat in [
        "Armazenamento",
        "Rede & Conectividade",
        "Balanceamento de Carga",
        "Cache & Dados In-Memory",
        "Segurança, Logs & Certificados",
    ]:
        assert result.categories_breakdown[cat] == []


def test_orphan_analyzer_comprehensive():
    vol = _make_resource("vol-1", "ec2:volume", "ec2")
    eip = _make_resource("1.2.3.4", "ec2:elastic-ip", "ec2")
    alb = _make_resource("alb-1", "elasticloadbalancing:loadbalancer/app", "elasticloadbalancing")
    log = _make_resource("/aws/lambda/test", "logs:log-group", "logs")
    cache_user = _make_resource("user-orphan", "memorydb:user", "memorydb", region="sa-east-1")
    other_irrelevant = _make_resource("i-12345", "ec2:instance", "ec2")

    data = _make_report_data([vol, eip, alb, log, cache_user, other_irrelevant])
    result = analyze_orphaned_resources(data)

    assert result.total_candidates == 5
    assert result.confirmed_orphans_count == 1  # cache_user
    assert result.potential_orphans_count == 4  # vol, eip, alb, log
    # 8.00 (vol) + 3.65 (eip) + 22.50 (alb) + 1.50 (log) + 0.00 (cache) = 35.65
    assert result.total_estimated_monthly_waste_usd == pytest.approx(35.65, 0.01)
    assert len(result.playbooks) == 5

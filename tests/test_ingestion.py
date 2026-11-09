import pytest
from pathlib import Path
from src.ingestion import load_and_deduplicate_csvs

def test_load_and_deduplicate_merges_files(tmp_path: Path):
    file1 = tmp_path / "resources.csv"
    file2 = tmp_path / "ec2.csv"
    
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row1 = "i-111,arn:aws:ec2:ca-central-1:807445251352:instance/i-111,ec2:instance,ca-central-1,807445251352,-,AWS::EC2::Instance,2026-10-10 10:00:00,ec2,0\n"
    row2 = "i-222,arn:aws:ec2:ca-central-1:807445251352:instance/i-222,ec2:instance,ca-central-1,807445251352,-,AWS::EC2::Instance,2026-10-10 10:00:00,ec2,0\n"
    # row1 again in ec2.csv with newer timestamp, non-zero tags, and cfn_type
    row1_newer = "i-111,arn:aws:ec2:ca-central-1:807445251352:instance/i-111,ec2:instance,ca-central-1,807445251352,-,AWS::EC2::Instance,2026-10-15 12:00:00,ec2,3\n"
    
    file1.write_text(header + row1 + row2, encoding="utf-8")
    file2.write_text(header + row1_newer, encoding="utf-8")
    
    records = load_and_deduplicate_csvs(str(tmp_path))
    
    assert len(records) == 2
    rec1 = next(r for r in records if r.identifier == "i-111")
    assert rec1.last_reported_at == "2026-10-15 12:00:00"
    assert rec1.tags == "3"
    assert set(rec1.source_files) == {"resources.csv", "ec2.csv"}

def test_load_and_deduplicate_handles_encoding_fallback(tmp_path: Path):
    latin_file = tmp_path / "latin.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row = "regra-1,arn:aws:config:sa-east-1:123:rule/1,config:rule,sa-east-1,123,-,AWS::Config::Rule,2026-10-10,config,0\n"
    latin_file.write_bytes((header + row).encode("iso-8859-1"))
    
    records = load_and_deduplicate_csvs(str(tmp_path))
    assert len(records) == 1
    assert records[0].identifier == "regra-1"

def test_load_and_deduplicate_fallback_key_when_arn_missing(tmp_path: Path):
    file1 = tmp_path / "custom.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row1 = "custom-id,,custom:res,sa-east-1,123,-,-,2026-10-10,custom,0\n"
    row2 = "custom-id,,custom:res,sa-east-1,123,-,AWS::Custom::Res,2026-10-11,custom,2\n"
    file1.write_text(header + row1 + row2, encoding="utf-8")

    records = load_and_deduplicate_csvs(str(tmp_path))
    assert len(records) == 1
    rec = records[0]
    assert rec.identifier == "custom-id"
    assert rec.cfn_resource_type == "AWS::Custom::Res"
    assert rec.tags == "2"
    assert rec.last_reported_at == "2026-10-11"

def test_load_and_deduplicate_empty_directory(tmp_path: Path):
    records = load_and_deduplicate_csvs(str(tmp_path))
    assert records == []

def test_load_and_deduplicate_skips_empty_or_blank_rows(tmp_path: Path):
    file1 = tmp_path / "blank.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    blank_row = ",,,,,,,,,\n"
    file1.write_text(header + blank_row, encoding="utf-8")

    records = load_and_deduplicate_csvs(str(tmp_path))
    assert len(records) == 0

def test_load_and_deduplicate_extracts_explicit_name(tmp_path: Path):
    file1 = tmp_path / "ec2_named.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags,Name\n"
    row = "i-111,arn:aws:ec2:ca-central-1:807445251352:instance/i-111,ec2:instance,ca-central-1,807445251352,-,AWS::EC2::Instance,2026-10-10,ec2,1,web-app-prod\n"
    file1.write_text(header + row, encoding="utf-8")

    records = load_and_deduplicate_csvs(str(tmp_path))
    assert len(records) == 1
    assert records[0].resource_name == "web-app-prod"

def test_load_and_deduplicate_name_fallback_heuristic(tmp_path: Path):
    file1 = tmp_path / "resources.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    # Opaque EC2 instance ID -> should remain "-"
    row_ec2 = "i-090d9b01ccf2af5ae,arn:aws:ec2:ca-central-1:807445251352:instance/i-090d9b01ccf2af5ae,ec2:instance,ca-central-1,807445251352,-,AWS::EC2::Instance,2026-10-10,ec2,0\n"
    # Opaque UUID -> should remain "-"
    row_acm = "4ce2fcfd-71be-4906-890b-e27700da3c77,arn:aws:acm:ca-central-1:807445251352:certificate/4ce2fcfd-71be-4906-890b-e27700da3c77,acm:certificate,ca-central-1,807445251352,-,AWS::CertificateManager::Certificate,2026-10-10,acm,0\n"
    # Friendly RDS identifier -> should be adopted
    row_rds = "canaisdb-02,arn:aws:rds:ca-central-1:807445251352:db:canaisdb-02,rds:db,ca-central-1,807445251352,-,AWS::RDS::DBInstance,2026-10-10,rds,0\n"
    # Friendly S3 identifier -> should be adopted
    row_s3 = "multicanais-db-00,arn:aws:s3:::multicanais-db-00,s3:bucket,ca-central-1,807445251352,-,AWS::S3::Bucket,2026-10-10,s3,0\n"
    file1.write_text(header + row_ec2 + row_acm + row_rds + row_s3, encoding="utf-8")

    records = load_and_deduplicate_csvs(str(tmp_path))
    assert len(records) == 4
    by_id = {r.identifier: r for r in records}
    assert by_id["i-090d9b01ccf2af5ae"].resource_name == "-"
    assert by_id["4ce2fcfd-71be-4906-890b-e27700da3c77"].resource_name == "-"
    assert by_id["canaisdb-02"].resource_name == "canaisdb-02"
    assert by_id["multicanais-db-00"].resource_name == "multicanais-db-00"

def test_load_and_deduplicate_merges_explicit_name_when_available(tmp_path: Path):
    file1 = tmp_path / "resources.csv"
    file2 = tmp_path / "ec2_tags.csv"
    header1 = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row1 = "i-111,arn:aws:ec2:ca-central-1:807445251352:instance/i-111,ec2:instance,ca-central-1,807445251352,-,AWS::EC2::Instance,2026-10-10,ec2,0\n"
    header2 = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags,tag:Name\n"
    row2 = "i-111,arn:aws:ec2:ca-central-1:807445251352:instance/i-111,ec2:instance,ca-central-1,807445251352,-,AWS::EC2::Instance,2026-10-10,ec2,1,portal-web\n"
    file1.write_text(header1 + row1, encoding="utf-8")
    file2.write_text(header2 + row2, encoding="utf-8")

    records = load_and_deduplicate_csvs(str(tmp_path))
    assert len(records) == 1
    assert records[0].resource_name == "portal-web"


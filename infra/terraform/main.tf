# Project Atlas — cloud infrastructure (AWS reference).
#
# Provisions the managed datastores and a Kubernetes cluster that the app
# (infra/k8s) deploys onto. This is a credible starting skeleton, not a
# turn-key production stack — review security groups, encryption, backups,
# and HA before going live. Run `terraform init && terraform plan` to review.
#
# Neo4j: AWS has no first-party managed Neo4j. Use Neo4j AuraDB (managed) or
# the Neo4j Helm chart on this EKS cluster, and feed its bolt URI into the
# app's NEO4J_URI (k8s ConfigMap). Tracked via the `neo4j_uri` output note.

locals {
  name = var.project
  tags = {
    Project   = "project-atlas"
    ManagedBy = "terraform"
  }
}

# ---- Networking ----
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name}-vpc"
  cidr = var.vpc_cidr

  azs             = ["${var.region}a", "${var.region}b", "${var.region}c"]
  private_subnets = ["10.40.1.0/24", "10.40.2.0/24", "10.40.3.0/24"]
  public_subnets  = ["10.40.101.0/24", "10.40.102.0/24", "10.40.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true
  tags               = local.tags
}

# ---- Kubernetes (EKS) ----
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${local.name}-eks"
  cluster_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    default = {
      instance_types = var.node_instance_types
      min_size       = 2
      max_size       = 10
      desired_size   = var.node_desired_size
    }
  }
  tags = local.tags
}

# ---- PostgreSQL (RDS) — system of record ----
module "postgres" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier        = "${local.name}-postgres"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.postgres_instance_class
  allocated_storage = var.postgres_allocated_storage

  db_name  = "atlas"
  username = var.db_username
  password = var.db_password
  port     = 5432

  multi_az               = true
  vpc_security_group_ids = [aws_security_group.datastores.id]
  subnet_ids             = module.vpc.private_subnets

  backup_retention_period = 14
  storage_encrypted       = true
  tags                    = local.tags
}

# ---- Redis (ElastiCache) — cache + job queue ----
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name}-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name}-redis"
  description          = "Atlas cache + arq job queue"
  engine               = "redis"
  node_type            = var.redis_node_type
  num_cache_clusters   = 2
  automatic_failover_enabled = true
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.datastores.id]
  tags                 = local.tags
}

# ---- OpenSearch — search index ----
resource "aws_opensearch_domain" "search" {
  domain_name    = "${local.name}-search"
  engine_version = "OpenSearch_2.13"

  cluster_config {
    instance_type  = var.opensearch_instance_type
    instance_count = var.opensearch_instance_count
    zone_awareness_enabled = true
    zone_awareness_config { availability_zone_count = 2 }
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 100
  }

  encrypt_at_rest { enabled = true }
  node_to_node_encryption { enabled = true }
  tags = local.tags
}

# ---- Shared datastore security group ----
resource "aws_security_group" "datastores" {
  name_prefix = "${local.name}-datastores-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "From EKS nodes only"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

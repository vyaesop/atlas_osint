output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "postgres_host" {
  value       = module.postgres.db_instance_address
  description = "Set as POSTGRES_HOST in the k8s ConfigMap."
}

output "redis_url" {
  value       = "redis://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
  description = "Set as REDIS_URL in the k8s ConfigMap."
}

output "opensearch_endpoint" {
  value       = "https://${aws_opensearch_domain.search.endpoint}"
  description = "Set as OPENSEARCH_URL in the k8s ConfigMap."
}

output "neo4j_note" {
  value = "Provision Neo4j AuraDB or the Neo4j Helm chart separately; set NEO4J_URI accordingly."
}

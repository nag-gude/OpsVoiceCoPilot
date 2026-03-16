output "gateway_url" {
  description = "User-facing Gateway URL (open this in the browser)"
  value       = module.gateway.uri
}

output "agent_url" {
  description = "Agent service URL (internal; used by Gateway)"
  value       = module.agent.uri
}

output "tools_url" {
  description = "Tools service URL (internal; used by Agent)"
  value       = module.tools.uri
}

output "image" {
  description = "Built image URI in Artifact Registry"
  value       = module.foundation.image_uri
}

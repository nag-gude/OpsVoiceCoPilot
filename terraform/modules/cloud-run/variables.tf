variable "name" {
  description = "Cloud Run service name"
  type        = string
}

variable "location" {
  description = "GCP region for the service"
  type        = string
}

variable "image_uri" {
  description = "Container image URI"
  type        = string
}

variable "service_account_email" {
  description = "Email of the service account the Cloud Run service runs as (least privilege)"
  type        = string
}

variable "env" {
  description = "Environment variables for the container (key = value)"
  type        = map(string)
  default     = {}
}

variable "min_instance_count" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instance_count" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated invocations (allUsers invoker)"
  type        = bool
  default     = true
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8080
}

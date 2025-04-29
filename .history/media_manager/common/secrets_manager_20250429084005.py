"""Secrets management utilities."""
import os
from typing import Optional

DOCKER_SECRETS_PATH = "/run/secrets"

def get_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a secret from either Docker secrets or environment variables.
    Docker secrets take precedence over environment variables.
    
    Args:
        secret_name: Name of the secret
        default: Default value if secret is not found
        
    Returns:
        The secret value or default if not found
    """
    # Convert secret name to lowercase for file naming
    secret_file = secret_name.lower()
    
    # Check Docker secrets first
    docker_secret_path = os.path.join(DOCKER_SECRETS_PATH, secret_file)
    if os.path.exists(docker_secret_path):
        with open(docker_secret_path, "r", encoding="utf-8") as f:
            return f.read().strip()
            
    # Fall back to environment variable
    return os.environ.get(secret_name, default)

def get_required_secret(secret_name: str) -> str:
    """
    Get a required secret, raising an error if not found.
    
    Args:
        secret_name: Name of the secret
        
    Returns:
        The secret value
        
    Raises:
        ValueError: If the secret is not found
    """
    value = get_secret(secret_name)
    if value is None:
        raise ValueError(f"Required secret {secret_name} not found")
    return value
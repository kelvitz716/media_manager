"""Secrets management utilities."""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

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
        try:
            with open(docker_secret_path, "r", encoding="utf-8") as f:
                value = f.read().strip()
                # Log secret state (safely)
                prefix = value[:3] if len(value) > 3 else value
                has_colon = ':' in value
                logger.debug(f"Loaded secret {secret_name} from Docker secrets - prefix: {prefix}..., contains colon: {has_colon}")
                return value
        except Exception as e:
            logger.error(f"Error reading Docker secret {secret_name}: {e}")
    else:
        logger.debug(f"Docker secret not found at {docker_secret_path}")
            
    # Fall back to environment variable
    env_value = os.environ.get(secret_name)
    if env_value:
        prefix = env_value[:3] if len(env_value) > 3 else env_value
        has_colon = ':' in env_value
        logger.debug(f"Using environment variable for {secret_name} - prefix: {prefix}..., contains colon: {has_colon}")
        return env_value
    
    logger.debug(f"No secret found for {secret_name}, using default")
    return default

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
        logger.error(f"Required secret {secret_name} not found")
        raise ValueError(f"Required secret {secret_name} not found")
    return value
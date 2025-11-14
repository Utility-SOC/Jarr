# arr_omnitool/core/secure_storage.py
"""
Secure credential management using the keyring library.
Provides a central service for storing and retrieving sensitive data.
"""

import logging
try:
    import keyring
except ImportError:
    print("WARNING: keyring library not found. pip install keyring")
    keyring = None

logger = logging.getLogger(__name__)

# Use a single, consistent service name for the application
KEYRING_SERVICE_NAME = "ARROmniTool"

class SecureStorage:
    """A wrapper for the keyring library."""

    def __init__(self):
        if not keyring:
            logger.critical("Keyring library is not installed. Secure storage is DISABLED.")
        
    def set_credential(self, key: str, password: str):
        """
        Saves a credential to the OS secure vault.
        
        Args:
            key: The unique identifier (e.g., "jellyfin_api_key")
            password: The secret to store.
        """
        if not keyring:
            return
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, key, password)
            logger.info(f"Securely stored credential for: {key}")
        except Exception as e:
            logger.error(f"Failed to store credential for {key}: {e}", exc_info=True)

    def get_credential(self, key: str) -> str | None:
        """
        Retrieves a credential from the OS secure vault.
        
        Args:
            key: The unique identifier (e.g., "jellyfin_api_key")
        Returns:
            The stored secret or None if not found.
        """
        if not keyring:
            return None
        try:
            password = keyring.get_password(KEYRING_SERVICE_NAME, key)
            if password:
                logger.debug(f"Retrieved credential for: {key}")
            return password
        except Exception as e:
            logger.error(f"Failed to retrieve credential for {key}: {e}", exc_info=True)
            return None

    def delete_credential(self, key: str):
        """
        Deletes a credential from the OS secure vault.
        
        Args:
            key: The unique identifier (e.g., "jellyfin_api_key")
        """
        if not keyring:
            return
        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, key)
            logger.info(f"Deleted credential for: {key}")
        except keyring.errors.PasswordDeleteError:
            logger.warning(f"No credential found to delete for: {key}")
        except Exception as e:
            logger.error(f"Failed to delete credential for {key}: {e}", exc_info=True)
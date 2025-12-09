"""Secret model for encrypted credentials storage."""

from django.db import models


class Secret(models.Model):
    """Secret storage model with encryption at rest.
    
    Secrets are encrypted using Fernet symmetric encryption before storage.
    """
    
    SERVICE_TYPE_CHOICES = [
        ("azure", "Azure"),
        ("unifi", "UniFi"),
        ("synology", "Synology"),
        ("generic", "Generic"),
    ]
    
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this secret"
    )
    service_type = models.CharField(
        max_length=50,
        choices=SERVICE_TYPE_CHOICES,
        db_index=True,
        help_text="Service type: azure, unifi, synology, or generic"
    )
    key = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Secret key (e.g., 'azure_client_secret', 'unifi_password')"
    )
    encrypted_value = models.TextField(
        help_text="Encrypted secret value"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "secrets"
        ordering = ["service_type", "name"]
        unique_together = ["service_type", "key"]
    
    def __str__(self):
        return f"{self.name} ({self.service_type}/{self.key})"
    
    def set_value(self, value: str) -> None:
        """Encrypt and set the secret value.
        
        Args:
            value: Plain text value to encrypt and store
        """
        import sys
        sys.path.insert(0, str(__file__).replace('/jexida_dashboard/secrets_app/models.py', ''))
        from core.services.secrets import encrypt_value
        self.encrypted_value = encrypt_value(value)
    
    def get_value(self) -> str:
        """Decrypt and return the secret value.
        
        Returns:
            Decrypted plain text value
        """
        import sys
        sys.path.insert(0, str(__file__).replace('/jexida_dashboard/secrets_app/models.py', ''))
        from core.services.secrets import decrypt_value
        return decrypt_value(self.encrypted_value)


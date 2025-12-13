class ConfigurationError(Exception):
    """Base class for all configuration errors."""


class ConfigurationDiscriminatorError(ConfigurationError):
    """Error raised when there is a mismatch between the discriminator value,
    discriminator field name and/or discriminator mapping.
    """

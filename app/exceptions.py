from __future__ import annotations


class OpenHomeError(Exception):
    pass


class ServerNotRunningError(OpenHomeError):
    pass


class ServerAlreadyRunningError(OpenHomeError):
    pass


class ServerJarNotFoundError(OpenHomeError):
    pass


class ServerNotProvisionedError(OpenHomeError):
    pass


class ServerLimitError(OpenHomeError):
    pass


class AuthError(OpenHomeError):
    pass


class PropertiesParseError(OpenHomeError):
    pass


class IconProcessingError(OpenHomeError):
    pass


class TunnelError(OpenHomeError):
    pass


class DnsUpdateError(OpenHomeError):
    pass


class DockerError(OpenHomeError):
    pass


class ProvisioningError(OpenHomeError):
    pass

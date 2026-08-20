"""
Custom email backend that forces IPv4 for SMTP connections.
Fixes: [Errno 101] Network is unreachable on hosts (like Render) that
can't route to Gmail's IPv6 address.
"""
import smtplib
import socket
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend


class IPv4SMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        # Force IPv4 by only looking up AF_INET addresses
        addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        family, socktype, proto, canonname, sockaddr = addr_info[0]
        sock = socket.socket(family, socktype, proto)
        if timeout is not None:
            sock.settimeout(timeout)
        sock.connect(sockaddr)
        return sock


class EmailBackend(SMTPEmailBackend):
    """Drop-in replacement for django.core.mail.backends.smtp.EmailBackend
    that forces the SMTP connection over IPv4."""

    def open(self):
        if self.connection:
            return False
        connection_class = IPv4SMTP
        try:
            self.connection = connection_class(
                self.host, self.port, timeout=self.timeout
            )
            if self.use_tls:
                self.connection.ehlo()
                self.connection.starttls()
                self.connection.ehlo()
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except Exception:
            if not self.fail_silently:
                raise
            return False
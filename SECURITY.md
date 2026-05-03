# Security Policy

## Supported Versions

Only the latest release is actively supported. Critical vulnerabilities reported
against older versions will be considered on a case-by-case basis.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Use GitHub's [private vulnerability reporting](https://github.com/domik82/tropek/security/advisories/new)
to submit a report.

Include:
- Description of the vulnerability
- Steps to reproduce
- Affected version(s)

You can expect an initial response within 7 days.

## Deployment Considerations

TROPEK is designed for internal/private network deployment. The API and UI do not
include built-in authentication. If you expose TROPEK beyond a trusted network,
place it behind a reverse proxy with authentication (e.g., OAuth2 Proxy, Authelia).

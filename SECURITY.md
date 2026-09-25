# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in ha-atmos, please report it privately:

- **Preferred**: [GitHub private vulnerability reporting](https://github.com/marpi82/ha-atmos/security/advisories/new)
- **Alternative**: email marpi82.dev@google.com

Please do not create a public GitHub issue for security vulnerabilities.

## Supported Versions

Only the **latest release** receives security fixes.

## Tooling

- bandit, ruff `S`, pip-audit, CodeQL, gitleaks, and a weekly OpenSSF Scorecard workflow.

Gateway passwords live in the Home Assistant config entry. Do not log them. Do not commit bus captures.

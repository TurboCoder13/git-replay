# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| `0.1.x` | ✅        |
| `< 0.1` | ❌        |

## Reporting Security Issues

Please **do not** create public GitHub issues for security vulnerabilities.

### How to Report

1. **GitHub advisory** (preferred):
   [Private security advisory](https://github.com/TurboCoder13/git-replay/security/advisories/new)

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 3 business days
- **Initial assessment**: Within 7 business days
- **Fix timeline**: Depends on severity (critical issues prioritized)

## Security Practices

- Dependencies managed via Renovate
- CI includes secret scanning and dependency review
- GitHub Actions pinned to full commit SHAs
- Data pipeline reads public repositories only

# Security Policy

## Supported Versions

Security updates are currently only applied to the latest version of Oisha-OS.

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within this project, please report it to the maintainers directly. **Do not create a public GitHub issue for security-related bugs.**

Please send security reports to:
- **Email**: baxtiyor@jonbranding.uz
- **Telegram**: [@baxtiyorjong_gaziyev](https://t.me/baxtiyorjong_gaziyev)

Please include as much detail as possible, including:
1. Type of issue (e.g., buffer overflow, SQL injection, information disclosure).
2. The location of the issue (e.g., specific file, function, or endpoint).
3. A summary of the impact.
4. Steps to reproduce the vulnerability (or a proof of concept).

We will acknowledge receipt of your report within 48 hours and provide a timeline for resolution.

### Security Best Practices for Oisha-OS

1. **Never commit `.env` files**: Use `.env.example` as a template and keep your secrets in a local `.env` or use Google Cloud Secret Manager in production.
2. **Rotate API Keys**: Regularly rotate your Telegram API keys, Gemini API keys, and AmoCRM credentials.
3. **Use Least Privilege**: Ensure that service accounts used for GCP deployment have only the necessary permissions.

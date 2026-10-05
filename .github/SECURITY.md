# Security Policy

## Supported Versions

We actively maintain security patches for the current stable version of the PESUAuth API (5.x). Please use the latest release to ensure you have the latest security updates.

## Reporting a Vulnerability

If you discover a security vulnerability in PESUAuth API, please follow these guidelines to report it responsibly:

- **Do NOT open a public issue** to report security problems.
- Instead, contact the maintainers privately on the PESU Developer Group channel (`#pesu-dev`) on [PESU Discord](https://discord.gg/eZ3uFs2), or email them.
- Include as much detail as possible:
  - Steps to reproduce the issue
  - Impact of the vulnerability
  - Any suggested mitigations or fixes

We will acknowledge your report within 48 hours and keep you updated on the progress.

## Important Disclaimer

PESUAuth API acts solely as an API gateway for authenticating PESU credentials via the PESU Academy service.

- Credentials are sent only to PESU Academy, over HTTPS, through the API its mobile app uses. They are never stored or
  logged, and neither is the access token PESU Academy issues.
- Profile data is returned to the caller and not stored.
- PESU Academy's responses also contain personal data that the API does not return (such as photos, blood group, addresses, parents'
  details and marks); PESUAuth discards it as soon as the response is read.
- We **do not control or take responsibility** for any third-party applications or services that use this API.
- Users and developers should exercise caution when using or integrating with applications built on top of this API.
- Always verify the trustworthiness and security practices of any client application using PESUAuth.

## Security Best Practices for Users

- Always use HTTPS to access the API.
- Do not share your credentials.
- Keep your dependencies up to date.
- Use strong passwords and rotate them regularly.

## Third-Party Dependencies

PESUAuth API uses several open-source dependencies. We regularly monitor and update dependencies to patch known vulnerabilities.

## Disclaimer

While we strive to maintain high security standards, no software is entirely free from vulnerabilities. Use this software at your own risk.

Thank you for helping us keep PESUAuth API secure!

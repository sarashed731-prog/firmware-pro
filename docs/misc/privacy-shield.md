# Privacy Shield Framework

This document defines a practical privacy shield for the OneKey ecosystem.
It is intended for firmware, client, backend, CI, and support workflows.

## 1) Scope definition

The privacy shield covers:

- **Data types**: seed phrases, private keys, passphrases, PIN-related metadata, addresses, transaction metadata, device identifiers, diagnostics, and support artifacts.
- **Systems**: firmware, companion apps, backend services, CI/CD pipelines, analytics, logging systems, and support tooling.
- **Users and actors**: end users, maintainers, support staff, security researchers, and third-party processors.
- **Requirements baseline**: applicable privacy laws and contractual obligations in each release region.

## 2) Data flow mapping

For each system, maintain a data-flow map that records:

- collection entry points
- processing purpose
- storage location and retention
- internal and external sharing paths
- deletion mechanism and SLA

Every map must include identified exposure points and corresponding mitigations.

## 3) Data minimization

Apply collection and retention controls by default:

- collect only data required for security, operation, or compliance
- avoid collecting raw secrets in logs, telemetry, crash dumps, and support exports
- define and enforce retention windows with automatic deletion
- require review for any new field added to telemetry or diagnostics

## 4) Protection controls

Minimum controls:

- encryption in transit on all data links
- encryption at rest for stored sensitive data
- centralized key lifecycle management (generation, rotation, revocation)
- strict access control with least-privilege roles and periodic review

## 5) Privacy-by-default behavior

Default product and platform settings must:

- use least privilege across services and operators
- require explicit opt-in for optional data sharing
- mask or redact sensitive fields in logs, UI diagnostics, and support outputs
- prefer local processing when remote transmission is not required

## 6) Monitoring and incident response

Implement continuous monitoring with:

- audit logging for access to sensitive systems and data
- anomaly detection for unusual access or data export behavior
- incident runbooks for privacy events, including containment, triage, notification, and remediation
- post-incident reviews with corrective actions and owners

## 7) Governance and rights handling

Establish governance for:

- consent capture and consent withdrawal workflows
- data subject rights requests (access, correction, deletion, portability where required)
- accountable ownership for privacy controls
- periodic policy and control reviews with documented outcomes

## 8) Continuous validation

Validate privacy controls as a recurring activity:

- include privacy and security tests in release validation
- verify minimization, masking, retention, and deletion controls
- review high-risk changes before release
- track findings to closure and update this framework as risk evolves

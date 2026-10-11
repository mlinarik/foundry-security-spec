# Interface Contracts

- [openapi.json](openapi.json): operator and substrate HTTP endpoints, security and request/response envelopes. Prefixes are distinct authorization domains, even if development routes share a host.
- [config.schema.json](config.schema.json): strict deployment/evaluation YAML-as-JSON schema.
- [example-config.json](example-config.json): placeholder-only example; not deployable until operator values are supplied.
- [runtime.md](runtime.md): role permissions, checkpoint adapter, tool/provider contracts, Kubernetes constraints and recovery.

Contract version 0.1.0. Requests and DTOs are validated before executing side effects. Operator credentials never derive from target text; agent authentication cannot reach control endpoints. The service exposes OpenAPI-compatible schemas for contract tests; implementation-generated OpenAPI must be compared with this design before release. No endpoint here is currently implemented. JSON Schema validates shape; runtime.md specifies required semantic and authorization checks.

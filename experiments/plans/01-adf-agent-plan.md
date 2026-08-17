# ADF Agent Plan

## Objective
Build an agent that helps teams design, troubleshoot, and optimize Azure Data Factory pipelines using natural language and repository-aware guidance.

## Core Use Cases
- Generate ADF pipeline and data flow definitions from business requirements
- Explain existing pipeline dependencies and failure points
- Suggest parameterization and reusable patterns
- Generate ARM/Bicep templates and deployment guidance
- Recommend performance improvements for copy activities and data flows

## Agent Design
- Planner agent: interprets pipeline requests and creates implementation steps
- Pipeline authoring agent: generates JSON, ARM, or Bicep artifacts
- Troubleshooting agent: analyzes pipeline errors and recommends fixes
- Governance agent: checks naming conventions, security, and deployment standards

## Inputs
- ADF pipeline definitions
- Linked service and dataset metadata
- Pipeline run logs
- GitHub or Azure DevOps repository context
- Data source and sink schemas

## Outputs
- Pipeline design suggestions
- Updated JSON/Bicep definitions
- Diagnostic summaries
- Deployment and rollback guidance

## Implementation Phases
1. Discovery and repository ingestion
2. Prompt templates for pipeline generation and troubleshooting
3. Tool integration with Azure Resource Manager and pipeline metadata APIs
4. Validation, test cases, and human approval workflow
5. Production rollout with logging and auditability

## Tooling Stack
- Azure Data Factory REST APIs
- Azure Resource Manager
- Azure DevOps or GitHub Actions
- Python SDKs for Azure management
- LLM orchestration layer with retrieval and memory

## Success Metrics
- Reduction in pipeline build time
- Fewer manual debugging cycles
- Higher template consistency
- Improved deployment confidence

## Risks and Mitigations
- Risk: incorrect JSON structure
  - Mitigation: schema validation and dry-run checks
- Risk: insecure secret usage
  - Mitigation: policy checks and secret redaction

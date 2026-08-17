# PR Review Agent Plan

## Objective
Create an agent that reviews data engineering pull requests for correctness, security, scalability, and compliance before merge.

## Core Use Cases
- Review SQL, PySpark, Python, and ADF changes for quality issues
- Detect missing tests, risky patterns, and regressions
- Summarize change impact for reviewers
- Suggest improvements for performance and maintainability
- Enforce repository standards and governance

## Agent Design
- Diff analysis agent: inspects changed files and context
- Compliance agent: checks for secrets, policy violations, and naming issues
- Test coverage agent: recommends missing verification steps
- Reviewer summary agent: generates concise PR feedback

## Inputs
- Pull request diff and metadata
- Repository structure and coding standards
- Previous PR history and review comments
- Test and deployment configuration

## Outputs
- Structured review comments
- Risk and impact summaries
- Suggested follow-up actions
- Merge readiness recommendations

## Implementation Phases
1. Connect to GitHub or Azure DevOps PR APIs
2. Create review rules for SQL, Spark, Python, and IaC changes
3. Add evidence-based suggestions with links to standards
4. Integrate into CI pipelines and require approvals for critical changes
5. Tune feedback quality using human reviewer feedback

## Tooling Stack
- GitHub or Azure DevOps APIs
- Python-based diff analysis
- LLM-based summarization and recommendation layer
- CI/CD pipeline integration
- Repository linting and static analysis tools

## Success Metrics
- Faster PR turnaround time
- Better consistency in code reviews
- Fewer post-merge defects
- Stronger governance compliance

## Risks and Mitigations
- Risk: low-quality or noisy review comments
  - Mitigation: use rule-based checks and confidence thresholds
- Risk: false positives on legitimate patterns
  - Mitigation: allow reviewer override and feedback loop

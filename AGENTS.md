# Agent Instructions

This repository is the canonical Copier template for the reusable Python/C++ project skeleton.

## Read first

Before changing the template, read:

1. `README.md`;
2. `template/docs/development/PROJECT_SKELETON_CONTRACT.md`;
3. the focused template, bootstrap, validation, and acceptance files for the behavior being changed.

For cross-repository ownership, ART composition, Docker/CodeBinder publication, and downstream propagation, read:

https://github.com/ScottChiuNYC/agentic-repo-template/blob/main/docs/ecosystem-architecture.md

## Ownership rules

- This repository owns build/package/dependency/test/CI skeleton behavior and `.copier-answers.pypackage-cpp.yml`.
- It does not own ART's `.copier-answers.art.yml`, generated agent router, or PDF publication workflow.
- It owns only its CodeBinder drop-in: `.codebinderignore.d/pypackage-cpp`.
- Do not consolidate independently owned CodeBinder fragments into a shared generated file.
- Treat the generated Project Skeleton Contract as project-local authority for repository mechanics.

## Change rules

- Validate template behavior with the repository's existing bootstrap and template-acceptance paths.
- For a change intended for existing projects, use a genuine Copier update and inspect preservation of project-owned/domain-owned content.
- Do not substitute hand-edited downstream files for a claimed Copier migration.
- Keep infrastructure changes separate from domain implementation changes.
- Prefer focused pull requests and squash merges after applicable validation passes.

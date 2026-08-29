# Changelog

All notable changes to this project are documented here. The format is based
on Keep a Changelog, and this project adheres to Semantic Versioning.

## [0.1.0] - 2026-08-29

### Added
- Monorepo structure: backend/, frontend/, infra/, docs/, scripts/, .github/
- Requirements source relocated to docs/requirements-prompt.txt
- Design system spec at frontend/DESIGN.md
- GitHub Spec Kit integration (opencode) with project constitution v1.0.0
- Agent skills installed: ui-ux-pro-max suite, frontend-design,
  react-best-practices, web-design-guidelines, shadcn, tdd, code-review,
  domain-modeling (project) and find-skills (global)
- Kalameh font family staged at frontend/src/fonts/kalameh (standard + FaNum
  webfont variants, 4 weights each, with FontLicense.txt)
- AGENTS.md guides at root, backend/, frontend/
- Bilingual implementation review documents (docs/reviews/en + fa):
  roadmap, 13-layer engineering review, skills & tooling, improvements
- Repository meta: README, CHANGELOG, VERSION, .gitignore, .gitattributes

### Changed
- None

### Fixed
- None

### Security
- Environment-driven configuration policy established; secrets excluded via
  .gitignore (.env ignored, .env.example only)

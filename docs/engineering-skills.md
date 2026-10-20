# DeliveryGap engineering skills

The reusable skills are packaged at [`deliverygap-engineering-plugin/`](../deliverygap-engineering-plugin/), using the portable Codex skills-only plugin layout:

```text
deliverygap-engineering-plugin/
  plugin.json
  skills/<skill-name>/SKILL.md
```

## Discovery and invocation

Correction to the earlier report: Codex supports repository-local discovery under `.agents/skills`. All 16 [repository entrypoints](../.agents/skills/) route to the maintained plugin instructions. No global installation or marketplace is required. Official reference: [Where Codex loads local skills](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills).

Launch Codex in this workspace and use `/skills` or `$frontend-engineer`, `$fastapi-architect`, `$qa-testing-engineer`, or `$deliverygap-orchestrator`. Restart the client if its selector has not refreshed. An explicit-path fallback is also available:

```text
Read and apply E:\PureLogics\final project\deliverygap-engineering-plugin\skills\frontend-engineer\SKILL.md
```

Explicit canonical-file invocation was verified in three read-only delegated sessions (frontend, backend/database, QA). On 17 October 2026, the installed Codex CLI 0.162.1 app-server `skills/list` with `forceReload: true` returned all 16 repository entrypoints with scope `repo`, enabled, and no errors. This verifies runtime discovery, not that every client has refreshed its current selector. The earlier assertion that the CLI lacked plugin installation commands was also incorrect: `codex plugin add --help` confirms them, but no plugin installation is needed for these local skills.

Reproduce discovery from the workspace root with `node scripts/verify_skill_discovery.mjs <absolute-path-to-codex.exe>`. This uses initialize/skills-list JSON-RPC and makes no model calls or global configuration changes.

## Validation

Each skill has a required `SKILL.md` and passes the bundled `quick_validate.py` validator. The package manifest parses successfully and contains 16 skills: the master orchestrator plus 15 specialists.

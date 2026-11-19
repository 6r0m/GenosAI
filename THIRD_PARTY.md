# Third-party material

GenosAI's original code, documentation and skills use the [MIT License](LICENSE).
The material below retains its own licenses and notices, which must accompany redistribution.

| Material | Provenance owner | Bundled terms |
|---|---|---|
| Frontend design skill | [pinned upstream commit](agents/skills/frontend-design/UPSTREAM.lock) | [Apache-2.0](agents/skills/frontend-design/LICENSE.txt) |
| Web interface guidelines reference | [pinned upstream commit](agents/skills/web-design-review/UPSTREAM.lock) | [MIT](agents/skills/web-design-review/references/vendor/web-interface-guidelines/LICENSE) |
| Playwright CLI reference manual | [@playwright/cli 0.1.17](agents/skills/drive-browser/UPSTREAM.lock) | [Apache-2.0](agents/skills/drive-browser/references/playwright-cli/LICENSE) |

The Playwright manual and license were verified against the same pinned npm archive. Provider SDKs,
model files and synced skill caches are not vendored in the source distribution. Pi's install lock
pins acquired runtime dependencies; their package notices remain in the installed dependency tree.
Model download recipes identify upstream repositories but convey no model redistribution rights.

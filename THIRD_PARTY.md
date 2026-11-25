# Third-party material

GenosAI's original code, documentation and skills use the [MIT License](LICENSE),
with initial attribution to the maintainer's public handle, `6r0m`.
The material below retains its own licenses and notices, which must accompany redistribution.

| Material | Provenance owner | Bundled terms |
|---|---|---|
| JSONC parser | [json-with-comments 1.3.0, local patches](agents/vendor/jsonc/UPSTREAM.lock) | [MIT](agents/vendor/jsonc/LICENSE) |
| Anthropic visual-direction reference | [Anthropic upstream pin](agents/skills/frontend-design/UPSTREAM.lock) | [Apache-2.0](agents/skills/frontend-design/references/vendor/anthropic/LICENSE.txt) |
| Web interface guidelines reference | [pinned upstream commit](agents/skills/web-design-review/UPSTREAM.lock) | [MIT](agents/skills/web-design-review/references/vendor/web-interface-guidelines/LICENSE) |
| Playwright CLI reference manual | [@playwright/cli 0.1.17](agents/skills/drive-browser/UPSTREAM.lock) | [Apache-2.0](agents/skills/drive-browser/references/playwright-cli/LICENSE) |

The Playwright manual and license were verified against the same pinned npm archive. Provider SDKs,
model files and synced skill caches are not vendored in the source distribution. Pi's install lock
pins acquired runtime dependencies; their package notices remain in the installed dependency tree.
The optional [Pi image-budget dependency](agents/providers/pi/plugins/README.md) is acquired at its
pinned Git commit during managed installation. The checkout includes its upstream MIT license.
Model download recipes identify upstream repositories but convey no model redistribution rights.

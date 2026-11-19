# Configuration parser dependency

[jsonc](jsonc/UPSTREAM.lock) pins the comment preprocessing module from MIT-licensed `json-with-comments`.
Its [license](jsonc/LICENSE) accompanies distribution. Only `_util.py` is vendored. The local patch replaces comments with whitespace,
preventing invalid adjacent tokens from becoming valid JSON. The configuration owner
uses that preprocessor and the standard-library strict JSON decoder, preserving duplicate
key checks and rejecting trailing commas. Unused upstream encoders are not bundled. Configuration regression tests cover those changes. No package
installation or network access is needed to read local settings.

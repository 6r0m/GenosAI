# Managed Pi plugins

The managed launcher loads reviewed local entrypoints for the selected run. Set optional
`plugins` under the private `pi` configuration for every profile, or in an individual
profile. Options from the selected profile take precedence. Start a new `pi-sot` process
after editing the options. When first enabling `image-budget`, run `make install PROVIDER=pi`
for the selected platform so the Pi package manager can acquire the fixed dependency.
Profiles share the verified checkout on each platform. Reapplying the same pin uses that local
checkout, and launching uses local files. The managed permission extension is required. To load
an extra CLI extension, supply an existing explicit local path. Raw Pi retains its own extension
acquisition workflow.

The supported `image-budget` plugin applies to the selected OpenAI-compatible image route.
It checks the outgoing JSON body, image count and any configured per-image constraints.
It keeps images introduced since the last completed answer and the configured number of
recent image occurrences. Identical screenshots each have their own position. The wire guard
protects every image in a request when it cannot align Pi's serialized images with those
positions. It may resize copies or replace older images with placeholders. Stored messages
and original image records remain available. Routine resizing is silent. The adapter reports
image omissions, recovery attempts, and refused requests.

For example, merge this plugin entry into an existing connection's `plugins` object:

```json
{
  "image-budget": {
    "maxRequestBytes": 41943040,
    "maxImages": 30,
    "maxInlineImageBytes": 33554432,
    "maxImageDimension": 8192,
    "denseImageCount": 15,
    "denseImageDimension": 4096,
    "protectRecent": 2
  }
}
```

Use limits appropriate to the endpoint. `maxRequestBytes` counts UTF-8 JSON bytes and
`maxInlineImageBytes` counts decoded image bytes. The dense limit applies at the given
final image count. `compress`, `compressMaxDimension` and `compressMaxBytes` tune old
image compression. `compressMaxBytes` measures base64 bytes.

A confirmed recoverable body-size or image-count rejection can trigger one smaller
retry in the same input. Pi retains normal compaction for token overflow and manual or
threshold compaction. The plugin scopes learned limits to the session branch, profile,
route, budget options and upstream revision. Learned limits survive reinstalling the same pin.
Its budget applies to normal agent requests with supported payload
ordering. Independent summary and nested SDK calls and foreign hooks that modify the
payload after the guard are outside this coverage.

The managed adapter consumes the unmodified planning, sizing, image processing and error
classification helpers from MIT-licensed [pi-image-budget](https://github.com/Aaalice233/pi-image-budget).
The [dependency owner](../runtime/image-engine.js) pins the Git commit, verifies the helper files,
and manages the owned checkout. It uses Pi's package acquisition API without registering the
upstream entrypoint. The checkout retains the upstream license. Route options and recovery
stay with GenosAI, so there is no separate operator-edited plugin file.

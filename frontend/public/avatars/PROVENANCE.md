# Agent avatar provenance

Brigade is the runtime identity registry and serves these files. Brand-Ops is
the source of mastered artwork where an identity comes from a product brand.

- `iris.webp` and its `thinking`, `success`, and `alert` variants were converted
  without semantic edits from the approved Brand-Ops Magic Unicorn Iris assets:
  `brand-kits/magic-unicorn/agents/iris/avatar*.png`.
- Source primary SHA-256:
  `8853aede2e78d073e743b79bcf919483831d41daf24847854ab40b7f0ec94b93`.
- `perry.webp` was converted without semantic edits from the approved
  Brand-Ops Magic Unicorn `perrywinkle-spector/avatar.png` master. The
  production source bytes identify as JPEG despite the legacy `.png` filename.
  Source SHA-256:
  `c18ebda7da6eccaa8ff623689cfb3b1e68ad68cc611d3df4266989803bcbd354`.
- `prudence.webp` was converted without semantic edits from the approved
  Brand-Ops Magic Unicorn `prudence-finch/avatar.png` master. The production
  source bytes identify as JPEG despite the legacy `.png` filename. Source
  SHA-256:
  `0ecae3dbf005571b853c86d96c5c8244c4aa230c8e99bc4ed381b12eb2c2374e`.
- `cpl.-colophon.webp` was converted without semantic edits from the approved
  Brand-Ops Magic Unicorn `cpl-colophon/avatar.png` master. The production
  source bytes identify as JPEG despite the legacy `.png` filename. Source
  SHA-256:
  `4860c7fa90ce29f1d8d6416405d51c71bda5eea559876e2d920aba1dd1015550`.
- `rating-raider.webp` is the exact 512x512 WebP already served by Brigade and
  explicitly bound to the production `rating-raider` identity before its
  import into source control. Runtime asset SHA-256:
  `4f4691c2eaa2989c1e249999c75f3f6c528515d96018e18caf2e4b023bbd06a3`.
- The original 17 Brigade portraits and their state variants predate this
  provenance manifest and remain Brigade-owned.

Do not bind an agent ID to a portrait based on title, rank, or visual
similarity. Add a mapping only when the identity owner provides an explicit
master or manifest.

## Stable resident portraits (2026-07-31)

- `majik.webp`, `sidekick.webp`, `corporal-qwen.webp` — verified primary
  portraits for the Stable residents. Explicit masters generated through
  Brand-Ops' compliance-checked agent-identity pipeline (brand
  `magic-unicorn`, slugs `majik` / `sidekick` / `corporal-qwen`; color-palette
  compliance pass, score 100 each). Brand-Ops manifests are the
  identity-owner evidence; production rows were bound explicitly the same day
  (runtime binding, rating-raider precedent) to CDN-busted `-v2.png` URLs,
  then promoted into the verified WebP set.
- Source PNG masters (1024×1024; `-v2.png` is byte-identical content used for
  Cloudflare cache-busting until the webp URLs ship):
  - `majik.png` / `majik-v2.png` SHA-256:
    `1768f8637254355b5c0c9936a4eeef3116e271cbad51550374bdd9bd4c1ef25c`
  - `sidekick.png` / `sidekick-v2.png` SHA-256:
    `4c6dbbf154eb614fbbe4d08cad18b99ee771a442516c6ad8f259b6c3e5dcf45a`
  - `corporal-qwen.png` / `corporal-qwen-v2.png` SHA-256:
    `517b5c1beef516fdcc4fa356f48731b3396b8fca467ed9641a719f72b7751e13`
- Verified WebP (re-encode, no semantic edit) SHA-256:
  - `majik.webp`:
    `dbca3e97d724984d62c2bf839c98abce567f9acd64f8713bceeda15376cbf49f`
  - `sidekick.webp`:
    `6e460c8d87437d4c01f05d9260175f9ae3d7a696411535ede6f3bed7181c2486`
  - `corporal-qwen.webp`:
    `eeaa747be5796da488103335a258641507e76687bfa8dcde67a04c717360636d`
- The `-v2.png` filenames remain in the catalog so production bindings that
  still point at them keep resolving until the migration rewrites rows to
  the canonical `.webp` paths.

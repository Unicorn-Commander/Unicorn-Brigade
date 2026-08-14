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

## Withdrawn portraits (2026-07-31)

`majik` and `sidekick` portraits were generated, briefly bound, and then
WITHDRAWN: the identity owner (Aaron) reviewed and rejected both art passes.
They were never approved masters, so the earlier "brand-ops-approved-master"
evidence strings for those two ids were incorrect and are removed here along
with the files and their verified-manifest entries. Their agent rows carry a
null avatar_url — consumers fall back deliberately — until approved
replacements exist. Do not re-add either id without a fresh owner sign-off.


## Character portraits — replacing logo emblems + new Ops app leads (2026-08-01)

Two batches, same locked recipe as the 2026-07-31 roster pass (chibi white
unicorn bust, thick black outlines, white sticker border, dark navy ground,
serious adult attitude — references `ref-general.webp`, `ref-gunny.webp`,
`corporal-qwen-v2.png`).

**Replaced logo emblems.** `cpl.-colophon`, `perry` and `prudence` were bound
to neon unicorn LOGO marks, not character portraits. The 2026-07-31 batch
skipped them because it selected on `avatar_url IS NULL`, and a bound row read
as done — bound is not the same as correct. Each now carries a portrait built
from its own rank and title (Chronicler / General Counsel / Consumer &
Compliance Counsel).

**New Ops app leads.** Portraits for the five app-lead identities registered so
every Ops app has a head in the org chart: Col. Ledger (Accounting-Ops CFO),
The Registrar (Contact-Ops), The Steward (Customer-Ops), Prof. Fathom (Center
Deep) and Capt. Cadence (Meeting-Ops).

Generated by the identity owner's own session on request (Aaron, 2026-08-01),
via our gateway; not inferred from name or visual similarity. `prudence` and
`center-deep-lead` are second passes — the first wrote garbled lettering onto
a clipboard and dark gloves in place of the style's white hooves.

- Master PNG SHA-256:
  - `cpl.-colophon-v2.png` SHA-256:
    `bd1de1bba7521e6efacb70a962b8c63249975cfd1bd28fdc4cca031bdb8272f7`
  - `perry-v2.png` SHA-256:
    `d7def262d7029c7d1108c86e44b5a28dc700379577409956fa07300f43194e46`
  - `prudence-v3.png` SHA-256:
    `11e49c27676a994a20fbacd80d80c40f71cf8bea1f21cea6973439783645de9e`
  - `accounting-ops-cfo-v1.png` SHA-256:
    `67e27a15050042aa43eba88fad3f785e95a761d958ae7036368626564e6b6c9e`
  - `contact-ops-lead-v1.png` SHA-256:
    `6d37ec0b9acd674bdda6b3990e5a22007c1e00258632d4b98bf682778fbbab87`
  - `customer-ops-lead-v1.png` SHA-256:
    `6dc7ea3034888ea003b68c5d1b0a6655089fcfe82637223758b3ed560bd90e1e`
  - `center-deep-lead-v2.png` SHA-256:
    `1a9281f3c468af9dd1e3206408d46be09ef3238f9254830d5818f84dd547d332`
  - `meeting-ops-lead-v1.png` SHA-256:
    `e29e77f7440c5f09a2eb9a233e10a699ceb59b40216948ea04d2d7cbb175ef36`

`majik` and `sidekick` remain deliberately unbound — see the withdrawal note
above. A null avatar_url on either id is intentional state, not a defect.


## Majik — APPROVED with a rainbow mane (2026-08-01)

**This supersedes the withdrawal note above FOR `majik` ONLY.** The identity
owner (Aaron) reviewed the withdrawn `majik-v4` composition on 2026-08-01 and
approved it subject to one change, verbatim: *"For Majik, it's basically what
you had for an avatar, just give him rainbow hair please."*

`majik-v5.png` is that composition — hooded arcane orchestrator, cosmic purple
robe, golden spiral horn, confident smirk — with the mane recoloured to a full
rainbow. Chosen over a second variant because the rainbow reads at 36px, the
size the Stable org chart renders these at.

- `majik-v5.png` SHA-256:
  `ded2b33de1de05a3bfd8ce9025d63ffea537ea22543f34ad65997625f36856c0`

`agents.avatar_url` for `majik` is now `/avatars/majik-v5.png`. A NULL there is
no longer the expected state — do not "restore" it.

**`sidekick` is still WITHDRAWN and still deliberately unbound.** A null
avatar_url on `sidekick` remains intentional state, not a defect, until the
owner approves art for it.

## Roster avatar backfill — 42 files brought into source control (2026-08-12/14)

A bulk "v2" migration had rewritten 41 of 55 roster rows to
`/avatars/<slug>-v2.png` files that were never generated, so those agents
rendered faceless. 36 replacement portraits were generated through Brand-Ops'
compliance-checked agent-identity pipeline (brand `magic-unicorn`, model
`gemini/gemini-3.1-flash-image` via litellm) against the locked roster recipe:
chibi white unicorn bust, thick black outlines, white sticker border, dark navy
ground, gold spiral horn, iridescent mane, serious adult attitude.

The generated art was written to Brigade's build context and `docker cp`'d into
the running `unicorn-brigade-ui` container, so URLs resolved — but the files
were never `git add`ed. They survived a rebuild only on that one host; a fresh
clone would have rebuilt the image without them and every one of those agents
would have gone faceless again. This entry records bringing all 42 untracked
`frontend/public/avatars/*.webp` files into source control.

- 42 files, 1,198,902 bytes total, every one a valid 512x512 WebP (RIFF/WEBP
  magic verified, all SHA-256s distinct — no duplicated or placeholder art).
- Nothing in `.gitignore` ever matched these paths. The files were simply never
  staged; `git check-ignore` confirms no rule applies. There is no ignore rule
  to fix.
- Per-file checksums are not reproduced here: unlike the earlier entries, these
  are not conversions of external masters, so the committed git blobs are
  themselves the provenance record.

**`sidekick` supersedes its withdrawal note.** The 2026-07-31 withdrawal above
says `sidekick` is deliberately unbound and a null `avatar_url` is intentional
state. That is no longer true: this batch generated `sidekick.webp` and the
production row is bound to `/avatars/sidekick.webp`. The file is committed here
because the repo was behind live reality, not because a fresh art approval was
recorded. **The identity owner should confirm this portrait**, since the
original rejection was an explicit owner decision.

**Two portraits are known off-family and are committed as-is pending
replacement**, because a wrong face still beats no face:

- `settlement-modeler.webp` — wears an olive-drab military cap and is composed
  as a wide shot over a glowing blueprint desk, with a literal red/orange/yellow
  rainbow mane. The roster is head-and-shoulders busts in dark navy/charcoal
  attire with a purple/cyan/magenta mane, and this agent is the Settlement
  Strategy Specialist (a legal analyst), so both the uniform and the desk are
  wrong for the role. Its brand-compliance score was 97/100 — the only
  non-perfect score in the batch — which caught the olive as an off-palette
  colour but could not see the wrong subject.
- `dr-glitter-mane.webp` — the lab coat and stethoscope suit the Chief Medical
  Officer role, but the execution is off-family: measured background luminance
  30 / RGB (20, 31, 60) against a roster median of 24 and a blue channel of
  38-44, making it the lightest and bluest ground in the set; the horn is a
  cyan-to-purple gradient rather than the roster's gold spiral; and the mane is
  silver-white with no iridescent colour.

Compliance scores rate palette, not subject. A 100/100 does not mean the
picture is right, and 97/100 did not mean this one was nearly right.

## dr-glitter-mane re-rolled on-family; settlement-modeler still open (2026-08-14)

`dr-glitter-mane.webp` REPLACED. The previous pass drifted from its own bio on
the three markers that define the roster: measured background luminance 30 /
RGB (20, 31, 60) against a roster band of 21-27 with blue 38-44 (the lightest
and bluest ground in the set), a cyan-to-purple horn instead of the gold spiral,
and a silver-white mane carrying none of the purple-to-cyan colour. The new pass
measures luminance 21 / RGB (16, 21, 40) — inside the band — with a gold horn
and a purple-to-cyan mane, keeping the white coat, stethoscope and caduceus that
were always correct. 512x512 WebP, 33,114 bytes, in line with the rest of the set.

`settlement-modeler.webp` UNCHANGED and still off-family. Two re-rolls were
attempted and both were worse than what is committed, so the original was kept:
a wrong face beats no face, and a worse face beats both.

**Why the bios were not the problem.** These agents did not have empty bios. Both
already carried the full locked recipe with exact hex codes, identical to the
bios of siblings that rendered correctly. The generator simply did not follow
them. Do not "fix" this by rewriting a bio that is already right.

**Negative constraints backfire on this model.** The second settlement-modeler
attempt spelled out "no tactical vest, no body armour, no MOLLE pouches, no
helmet". It returned a unicorn in a tactical helmet with a mounted optic and
antennas, wearing a plate carrier — the model attended to the nouns and dropped
the negation. The first attempt, which forbade the olive cap and the desk, did
drop both but invented a wireframe isometric background panel and a cyan horn
instead. State what the picture SHOULD contain; naming the unwanted object tends
to summon it. `dr-glitter-mane` succeeded on the first attempt under
positive-only phrasing, after settlement-modeler had failed twice under negative
phrasing.

**Compliance score is not a picture review.** Every one of these failures scored
100/100 on colour, including the tactical-helmet pass. The original
settlement-modeler scored 97/100 and the 3% offender was exactly the olive cap
(#4c5a41) — the check saw the one wrong colour and was blind to the wrong
uniform, the wrong crop and the missing scales. A palette check cannot tell you
the horn is the wrong colour when cyan is also a brand colour. Look at the image.

**Brand-Ops now diverges for settlement-modeler.** Its stored master under
`brand-kits/magic-unicorn/agents/settlement-modeler/avatar` is the rejected
tactical-helmet pass, because generation overwrites in place and there is no
revert. Brigade and Stable both still serve the original olive-cap portrait.
Regenerate before trusting the Brand-Ops master for that one slug. Its bio has
been reset to positive-only phrasing and is primed for another attempt.

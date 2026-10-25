# Unicorn Brigade design system

*Contract for every UI change. Built 2026-10-24 for the world-class pass; enforced by `npm run audit`.*

Brigade is the AI Agent Factory: where agents are built, configured, orchestrated and watched. The bar is Linear for interaction craft, Vercel and Raycast for calm dark-native polish, Retool and n8n for builder tools, and the best agent consoles for showing what agents are doing, live. Aaron's own reference is magicunicorn.dev: near-black, white type, system sans, small uppercase eyebrows, one rainbow word, real product screenshots, calm.

**One rule above all: primitives own geometry, call sites own composition.** A page decides *what* goes where; a primitive decides *how tall, how round, how loud*. If you are writing `px-`, `py-`, `text-[`, `rounded-lg`, `bg-slate-` or `#` in a page, stop and ask the primitive for a size or a tone instead.

## 1. Tokens (`src/styles/tokens.css`)

Colour tokens are HSL triples consumed by Tailwind as `hsl(var(--token) / <alpha>)`, so `bg-card/60` and `bg-ok/10` work. Dark is the default (`:root`); light lives on `:root[data-theme="light"]` and is flipped by `src/utils/theme.js`.

| Group | Tokens | Use |
|---|---|---|
| Surfaces | `bg` · `surface` · `card` · `elevated` · `overlay` | page → panel → card → nested tile → popover/dialog |
| Edges | `border` · `border-strong` | hairline between surfaces · input and active edges |
| Text | `fg-strong` · `fg` · `muted` · `subtle` | titles · body · secondary · placeholder/meta (all ≥ 4.5:1 on every surface) |
| Brand | `accent` · `accent-fill` · `on-accent` | text-safe accent · button fill · text on the fill |
| Status | `ok` · `warn` · `danger` · `info` · `live` (+ `*-fill`, `on-warn`) | success / caution / failure / neutral info / streaming & live signal |
| Focus | `ring` | the one focus ring |
| Radius | `rounded-chip` 6 · `rounded-control` 8 · `rounded-card` 12 · `rounded-pane` 16 · `rounded-full` | chips · buttons/inputs · cards · dialogs/sheets · avatars/pills |
| Elevation | `shadow-e1` … `shadow-e4` | hairline · card hover · popover/dock window · modal |
| Stacking | `z-raised` 10 · `z-sticky` 20 · `z-dock` 30 · `z-nav` 40 · `z-overlay` 50 · `z-modal` 60 · `z-popover` 70 · `z-toast` 80 · `z-tooltip` 90 | in that order, always |
| Motion | `duration-fast` 120 · `duration-base` 200 · `duration-slow` 320 · `ease-standard` · `ease-emphasized` | hover/press · enter/exit · layout; `animate-fade-in` / `animate-slide-up` / `animate-scale-in` |
| Gradients | `bg-gradient-accent` (primary button) · `.text-gradient-brand` (The General's rainbow) | the rainbow is a display moment: the wordmark or one hero word, never a heading style or a button |

Canvas, WebGL and xyflow code read the same tokens at runtime through `src/utils/tokens.js` (`tokenHsl('--ok', 0.4)`, `statusColors()`), so a theme flip reaches the graphs too.

### Type scale

`text-micro` 11/16 (the floor — nothing a person reads is smaller) · `text-caption` 12/16 · `text-body-sm` 13/18 · `text-body` 14/20 · `text-lead` 16/24 · `text-heading` 18/26 semibold · `text-title` 22/28 semibold · `text-display` 28/34 bold · `text-hero` 40/44. Font is the system sans; mono is the system mono.

Page titles are `text-title text-fg-strong` through `<PageHeader>`. Section titles are `text-heading`. Card titles are `text-lead font-semibold`. Everything else is body or smaller.

## 2. Primitives (`src/components/ui`, import from `../components/ui`)

| Primitive | What it owns |
|---|---|
| `Button` | variants primary · secondary · outline · ghost · danger · link; sizes xs 28 · sm 32 · md 36 · lg 44; `icon`, `iconRight`, `loading`, `iconOnly` (needs `aria-label`), `touch` |
| `IconButton` | square icon button with a required `label` (aria-label + tooltip) |
| `Field` + `Input` / `Textarea` / `Select` | label, help, error (announced), one geometry, one focus ring; sizes sm · md · lg |
| `Chip` | tones neutral · accent · ok · warn · danger · info · live; `solid`, `dot`, `pulse`, `uppercase`; toggle with `onClick` + `selected` |
| `StatusDot` + `AGENT_STATUS` | the shared agent-status vocabulary (idle · thinking · tool · responding · done · error · offline): colour, pulse, label — used by the chart, the activity wall, the dock, the chat and the feed |
| `Tooltip` + `TooltipHost` | hover + keyboard focus tooltips through one host (mounted in App) |
| `Tabs` | role=tablist, arrow keys, Home/End; variants underline · segmented |
| `EmptyState` / `ErrorState` / `OfflineState` / `LoadingState` | the four states; `LoadingState` variants cards · list · table · stats · text · chart |
| `PageHeader` / `Page` / `SectionHeader` | the page frame: eyebrow, plain title, description, actions, optional tabs and breadcrumbs; 16px gutters on phones, 24px from `sm` |
| `Card` + `CardHeader` / `CardBody` / `CardFooter` | variants default · glass · elevated; `interactive` for clickable cards |
| `Modal` | dialog semantics, focus trap + restore, Escape, scroll lock; `title`, `description`, `footer`, `tone="danger"`; full-width bottom sheet on phones |
| `Sheet` | drawer from the bottom (phones) or the right (side panels), same contract as Modal |
| `Menu` | dropdown of actions with full keyboard support, `tone: 'danger'` items |
| `DataTable` | a real table on desktop, a card list on phones; loading / error / empty built in |
| `Kbd` | keycaps so shortcuts are discoverable |
| `Spinner` | the only spinner — inline in a sentence or a button; never for a page load |
| `StatCard`, `Toggle`, `BarList`, `TimeSeriesChart` | existing, token-based |

`src/utils/errors.js` → `humanize(err)` turns any thrown thing into a sentence with a next step. The UI never shows a raw exception.

## 3. The exemplar: `src/pages/ToolLibrary.jsx`

Read it before touching any page. It is the whole contract in 300 lines:

1. `<Page>` + `<PageHeader eyebrow title description actions>` — one frame, plain title.
2. A toolbar in a `<Card padding="sm">` with `<Input type="search">` and `<Select>`s, each with an accessible name.
3. **All four states, in the place the content goes:** `LoadingState` (same grid shape, no layout shift), `ErrorState` (human words + Retry), `EmptyState` (what's missing + the next step; a *filtered-to-nothing* empty is a different, compact state with "Clear filters"), `OfflineState`.
4. Content on `<Card interactive as="button">` so every card is keyboard reachable; `Chip` carries type and status with one tone each.
5. Detail in `<Modal title description footer>`.
6. No dead ends: every button does something or isn't there.

## 4. Every state, every surface

A screen is not done until it has: **empty** (inviting, names the next step), **loading** (a skeleton of the real shape), **error** (recoverable, human words, a retry), **offline**. Use the shared renderers. Copy style: say what is missing, then what to do. "No scheduled runs yet. Schedule an agent to run on a cron and it appears here."

Agents must be **visibly alive**: who is working on what, who delegated to whom, what just failed and why — in a glance and without a refresh. `AGENT_STATUS` is the vocabulary; a failure always carries its reason in human words.

## 5. Keyboard, focus, accessibility (measured, not claimed)

- Every control is a real `<button>`, `<a href>`, or form control with an accessible name. Icon-only controls use `IconButton` or `aria-label`. A `title` attribute is not a tooltip.
- The global focus ring (`--ring`, 2px, offset 2px) applies to every control. Never `focus:outline-none` without a visible replacement; the primitives already pair it with a ring.
- Dialogs trap and restore focus; Escape closes everything (dialogs, sheets, menus, the palette, dock windows).
- Touch targets are 44px on phones (`touch` prop, `min-h-touch`), tables become card lists, drawers replace popovers.
- Contrast is enforced by `npm run audit:contrast` on every token pairing in both themes (4.5:1 text, 3:1 focus rings and status dots). "Verified AA" in a comment is not evidence; the gate is.
- Motion respects `prefers-reduced-motion` globally (index.css). Motion orients (enter/exit, state change); it never decorates.

## 6. The gates — `npm run audit`

- **`audit:contrast`** parses `tokens.css`, resolves both themes and fails on any pairing below threshold. Never lower a threshold; change the colour.
- **`audit:design`** is a **ratchet** over 16 violation classes (arbitrary font sizes, hex colours, raw slate/status/brand palette classes, off-token radius/shadow/z-index, hand-rolled modals, bare spinners, `title` tooltips, suppressed focus, gradient headings, inline colour styles, `!` overrides, raw error messages). Baseline `scripts/design-system-baseline.json`. **Counts may only go down.** `--report` shows every file:line and the fix; after a real reduction run `--bless` to lock the win in. Lanes land partial migrations safely: the app can only get better.

`npm run build` must be clean. A lane that regresses a gate does not merge.

## 7. How a lane works

1. Branch from the foundation. Run `npm run mock` (fixtures for every scenario: normal · large · empty · busy · error · slow) and `npm run dev:mock` to see your pages with real shapes in every state — no Docker, no login.
2. Convert a page: frame → toolbar → states → content → dialogs, replacing raw classes with primitives and tokens as you go. Delete, don't wrap: a page should get shorter.
3. Verify with the house screenshot tool at desktop (1440) and mobile (390), in `normal`, `empty`, `busy` and `error` scenarios; zero console errors, zero failed requests you didn't intend.
4. `npm run build && npm run audit` green; then `audit:design --bless` to record your reduction.
5. Commit with a message that names the surface and the states you designed. Disjoint file sets per lane; never touch `components/ui`, `tokens.css`, `tailwind.config.js`, `index.css` or `scripts/` — ask the integrator.

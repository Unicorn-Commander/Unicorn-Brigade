# Brigade Auth Components - Visual Guide

Visual reference showing how each component looks and behaves.

## 🎨 Component Previews

### TierBadge

Visual representation of all subscription tiers:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  Trial                                          │
│  ┌──────────────┐                              │
│  │ ✨ Trial     │  (Gray background)            │
│  └──────────────┘                              │
│                                                 │
│  Starter                                        │
│  ┌──────────────┐                              │
│  │ ⚡ Starter   │  (Blue background)            │
│  └──────────────┘                              │
│                                                 │
│  Professional                                   │
│  ┌──────────────────┐                          │
│  │ 👑 Professional │  (Purple background)      │
│  └──────────────────┘                          │
│                                                 │
│  Enterprise                                     │
│  ┌───────────────┐                             │
│  │ 🏢 Enterprise │  (Yellow background)         │
│  └───────────────┘                             │
│                                                 │
│  Founders                                       │
│  ┌──────────────┐                              │
│  │ ⭐ Founders  │  (Rainbow gradient)           │
│  └──────────────┘                              │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Hover Effect**: Scale 1.05, shows tooltip with benefits

### RoleBadge

Visual representation of all user roles:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  User                                           │
│  ┌──────────────┐                              │
│  │ 👤 User      │  (Gray background)            │
│  └──────────────┘                              │
│                                                 │
│  Builder                                        │
│  ┌──────────────┐                              │
│  │ 🔧 Builder   │  (Blue background)            │
│  └──────────────┘                              │
│                                                 │
│  Power Builder                                  │
│  ┌───────────────────┐                         │
│  │ ⚡ Power Builder │  (Purple background)      │
│  └───────────────────┘                         │
│                                                 │
│  Org Admin                                      │
│  ┌──────────────────┐                          │
│  │ 🛡️ Org Admin    │  (Orange background)      │
│  └──────────────────┘                          │
│                                                 │
│  Platform Admin                                 │
│  ┌─────────────────────┐                       │
│  │ 👑 Platform Admin  │  (Red background)       │
│  └─────────────────────┘                       │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Hover Effect**: Scale 1.05, shows tooltip with permissions

### UserProfile

User profile widget with dropdown:

```
┌─────────────────────────────────────────────────┐
│  Collapsed State:                               │
│  ┌──────────────────────────────────────────┐  │
│  │ ┌──┐                                      │  │
│  │ │DU│  demo-user                        ▼ │  │
│  │ └──┘  demo@unicorncommander.ai           │  │
│  └──────────────────────────────────────────┘  │
│                                                 │
│  Expanded State:                                │
│  ┌──────────────────────────────────────────┐  │
│  │ ┌──┐                                      │  │
│  │ │DU│  demo-user                        ▲ │  │
│  │ └──┘  demo@unicorncommander.ai           │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │                                          │  │
│  │ demo-user                                │  │
│  │ 📧 demo@unicorncommander.ai             │  │
│  │ [👑 Professional] [🔧 Builder]          │  │
│  │                                          │  │
│  │ ──────────────────────────────────────  │  │
│  │                                          │  │
│  │ ⚙️  Profile Settings                     │  │
│  │ 💳 Billing Dashboard                     │  │
│  │                                          │  │
│  │ ──────────────────────────────────────  │  │
│  │                                          │  │
│  │ 🚪 Sign Out                              │  │
│  │                                          │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

**Interactions**:
- Click to expand/collapse
- Click outside to close
- Hover items for highlight

### UpgradePrompt (Inline)

Inline upgrade banner:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │ 🔒  Upgrade Required                      │ │
│  │                                           │ │
│  │     This feature requires                │ │
│  │     [👑 Professional]                    │ │
│  │                                           │ │
│  │                      [ Upgrade →  ]      │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Colors**: Purple/pink gradient background

### UpgradePrompt (Modal)

Full-featured upgrade modal:

```
┌─────────────────────────────────────────────────┐
│                       [X]                        │
│  ┌───────────────────────────────────────────┐  │
│  │  ✨  Unlock Premium Features              │  │
│  │      Upgrade to access this feature       │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  Required: [👑 Professional] [🔧 Builder]       │
│  Your plan: [⚡ Starter] [👤 User]              │
│                                                  │
│  What you'll get:                               │
│  ✓ Access to advanced agent builder             │
│  ✓ Unlimited agent creation                     │
│  ✓ Publishing to marketplace                    │
│  ✓ Priority support                             │
│                                                  │
│  [ Maybe Later ]    [ Upgrade Now → ]           │
│                                                  │
└─────────────────────────────────────────────────┘
```

**Animation**: Fade in + scale, backdrop blur

### FeatureLock

Locked feature with blur overlay:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │                                           │ │
│  │  [Blurred Content Underneath]            │ │
│  │                                           │ │
│  │          ┌──────────┐                    │ │
│  │          │    🔒    │  (with glow)       │ │
│  │          └──────────┘                    │ │
│  │                                           │ │
│  │       Feature Locked                     │ │
│  │   Upgrade to unlock this feature         │ │
│  │                                           │ │
│  │      [👑 Professional]                   │ │
│  │                                           │ │
│  │   [ ✨ Upgrade Now ]                     │ │
│  │                                           │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Effect**: Medium blur (4px), white/60 overlay, lock icon with pulsing glow

### PermissionGate (Denied)

When permission denied, shows inline upgrade:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  [Content hidden because permission denied]    │
│                                                 │
│  Shows: <UpgradePrompt inline />               │
│                                                 │
└─────────────────────────────────────────────────┘
```

### RoleGate (Denied)

When role denied, shows inline upgrade:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  [Content hidden because role insufficient]    │
│                                                 │
│  Shows: <UpgradePrompt requiredRole="..." />   │
│                                                 │
└─────────────────────────────────────────────────┘
```

## 🎬 Interaction Flows

### Flow 1: User Tries to Create Agent (Permission Denied)

```
Step 1: User clicks "Create Agent"
┌──────────────────────┐
│ [ Create Agent ]     │  ← Click
└──────────────────────┘

Step 2: PermissionGate checks permission
if (!hasPermission('create_agents')) {
  return <UpgradePrompt inline />
}

Step 3: Inline upgrade prompt appears
┌─────────────────────────────────────────┐
│ 🔒  Upgrade Required                    │
│                                         │
│     This feature requires               │
│     [👑 Professional]                  │
│                                         │
│                  [ Upgrade →  ]        │
└─────────────────────────────────────────┘

Step 4: User clicks "Upgrade"
→ Opens Ops Center in new tab
→ https://unicorncommander.ai/plans.html
```

### Flow 2: User Hovers Over Tier Badge

```
Step 1: Cursor moves over badge
┌──────────────────┐
│ 👑 Professional │  ← Hover
└──────────────────┘

Step 2: Badge scales to 1.05

Step 3: Tooltip appears after 200ms delay
┌──────────────────┐
│ 👑 Professional │
└────────┬─────────┘
         │
         ▼
   ┌─────────────────────────┐
   │ Professional Plan       │
   │ ✓ 10,000 API calls/mo  │
   │ ✓ All services access  │
   │ ✓ Billing dashboard    │
   │ ✓ Priority support     │
   └─────────────────────────┘

Step 4: Cursor moves away
→ Tooltip disappears
→ Badge scales back to 1.0
```

### Flow 3: User Opens Profile Dropdown

```
Step 1: User clicks profile
┌──────────────────────────────┐
│ ┌──┐                          │
│ │DU│  demo-user            ▼ │  ← Click
│ └──┘  demo@...               │
└──────────────────────────────┘

Step 2: Dropdown animates in (opacity 0→1, y -10→0)

Step 3: Dropdown shows full menu
┌──────────────────────────────┐
│ ┌──┐                          │
│ │DU│  demo-user            ▲ │
│ └──┘  demo@...               │
└──────────────────────────────┘
┌──────────────────────────────┐
│ demo-user                    │
│ 📧 demo@...                  │
│ [👑 Professional] [🔧]      │
│ ──────────────────────────  │
│ ⚙️  Profile Settings         │
│ 💳 Billing Dashboard         │
│ ──────────────────────────  │
│ 🚪 Sign Out                  │
└──────────────────────────────┘

Step 4: User clicks outside
→ Dropdown animates out
→ Returns to collapsed state
```

### Flow 4: Feature Lock with Animation

```
Step 1: Page loads, feature is locked

Step 2: Lock icon animates in
- Scale: 0 → 1
- Rotate: -180deg → 0deg
- Spring animation (200ms stiffness)

Step 3: Glow animation starts (infinite loop)
- Scale: 1 → 1.3 → 1
- Opacity: 0.5 → 0 → 0.5
- Duration: 2s

Step 4: User clicks "Upgrade Now"
→ Modal upgrade prompt opens
→ Backdrop blurs and fades in
→ Modal scales from 0.95 to 1.0
```

## 🎨 Color Palette

### Tier Colors

```
Trial:        bg-gray-100    text-gray-700    border-gray-300
Starter:      bg-blue-100    text-blue-700    border-blue-300
Professional: bg-purple-100  text-purple-700  border-purple-300
Enterprise:   bg-yellow-100  text-yellow-700  border-yellow-300
Founders:     gradient       text-white       border-0
```

### Role Colors

```
User:          bg-gray-100    text-gray-700    border-gray-300
Builder:       bg-blue-100    text-blue-700    border-blue-300
Power Builder: bg-purple-100  text-purple-700  border-purple-300
Org Admin:     bg-orange-100  text-orange-700  border-orange-300
Platform Admin: bg-red-100    text-red-700     border-red-300
```

### Gradient (Purple/Pink Theme)

```
Primary:   from-purple-600 to-pink-600
Hover:     from-purple-700 to-pink-700
Background: from-purple-50 to-pink-50
```

## 📐 Sizing

### Badge Sizes

```
Small:  text-xs  px-2 py-0.5  icon-12px
Medium: text-sm  px-3 py-1    icon-14px
Large:  text-base px-4 py-1.5 icon-16px
```

### Blur Strengths

```
Light:  blur-[2px]
Medium: blur-[4px]
Heavy:  blur-[8px]
```

### Spacing

```
Component padding:    p-4, p-6
Section margins:      mb-4, mb-6, mb-8
Icon gap:             gap-2, gap-3
Border radius:        rounded-lg (8px), rounded-full
```

## 🔄 Animation Timings

```
Fast transitions:     150ms
Standard transitions: 200ms
Slow transitions:     300ms
Modal entrance:       0.15s ease
Badge hover:          0.2s ease
Dropdown:             0.15s ease
Lock glow pulse:      2s infinite
```

## 💡 Tips for Designers

### Consistent Spacing
- Use Tailwind spacing scale (4px increments)
- Maintain 16px or 24px between sections
- Use 8px or 12px for internal component spacing

### Icon Usage
- Lucide React icons at 16px, 20px, or 24px
- Always include icon with badges (optional via prop)
- Use semantic icons (Lock for locked, Crown for premium)

### Color Contrast
- All text meets WCAG AA contrast ratios
- White text on gradients (founders badge)
- Dark text on light backgrounds
- Light text on dark backgrounds

### Hover States
- Scale 1.05 for badges
- Background color darkening for buttons
- Underline for text links
- Shadow expansion for cards

### Mobile Considerations
- Touch targets minimum 44px
- Modals fill screen on mobile
- Tooltips work with tap (not just hover)
- Dropdowns expand to full width on small screens

---

This visual guide provides a reference for how components should look and behave. Actual implementation matches these designs with pixel-perfect precision using Tailwind CSS and Framer Motion.

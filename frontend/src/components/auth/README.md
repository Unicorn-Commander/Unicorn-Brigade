# Brigade Auth Component Library

Permission-based UI component library for Unicorn Brigade. This library provides reusable React components for implementing feature gating, subscription tiers, user roles, and upgrade prompts.

## Installation

All components are located in `/frontend/src/components/auth/` and can be imported directly:

```jsx
import { PermissionGate, RoleGate, TierBadge } from '../components/auth';
```

## Components

### 1. PermissionGate

Conditionally renders children based on user permissions.

**Props:**
- `permission` (string): Single permission to check
- `permissions` (array): Multiple permissions to check
- `requireAll` (boolean): If true, user must have ALL permissions. Default: false (OR logic)
- `fallback` (node): Custom fallback when permission denied
- `showUpgradePrompt` (boolean): Show upgrade prompt when denied. Default: true

**Examples:**

```jsx
// Single permission
<PermissionGate permission="create_agents">
  <CreateAgentButton />
</PermissionGate>

// Multiple permissions with AND logic
<PermissionGate permissions={["create_agents", "publish_agents"]} requireAll>
  <PublishButton />
</PermissionGate>

// Multiple permissions with OR logic
<PermissionGate permissions={["view_agents", "edit_agents"]}>
  <AgentList />
</PermissionGate>

// Custom fallback
<PermissionGate
  permission="advanced_features"
  fallback={<p>This feature is not available.</p>}
  showUpgradePrompt={false}
>
  <AdvancedPanel />
</PermissionGate>
```

### 2. RoleGate

Conditionally renders children based on user role.

**Props:**
- `role` (string): Single role to check
- `roles` (array): Multiple roles to check (OR logic)
- `minRole` (string): Minimum role level required (hierarchical)
- `fallback` (node): Custom fallback when role denied
- `showUpgradePrompt` (boolean): Show upgrade prompt when denied. Default: true

**Role Hierarchy:**
1. `brigade-user` (lowest)
2. `brigade-builder`
3. `brigade-power-builder`
4. `brigade-org-admin`
5. `brigade-platform-admin` (highest)

**Examples:**

```jsx
// Single role
<RoleGate role="brigade-builder">
  <AgentBuilderPanel />
</RoleGate>

// Multiple roles (OR logic)
<RoleGate roles={["brigade-builder", "brigade-power-builder"]}>
  <AdvancedFeatures />
</RoleGate>

// Minimum role level (hierarchical)
<RoleGate minRole="brigade-power-builder">
  <PublishToMarketplace />
</RoleGate>
```

### 3. TierBadge

Displays a color-coded badge for subscription tiers.

**Props:**
- `tier` (string): Subscription tier (required)
  - `trial`, `starter`, `professional`, `enterprise`, `founders`
- `size` (string): Badge size. Default: `medium`
  - `small`, `medium`, `large`
- `showIcon` (boolean): Show tier icon. Default: true
- `className` (string): Additional CSS classes

**Examples:**

```jsx
// Basic usage
<TierBadge tier="professional" />

// Large badge without icon
<TierBadge tier="enterprise" size="large" showIcon={false} />

// Small badge with custom class
<TierBadge tier="starter" size="small" className="ml-2" />
```

### 4. RoleBadge

Displays a color-coded badge for user roles.

**Props:**
- `role` (string): User role (required)
  - `brigade-user`, `brigade-builder`, `brigade-power-builder`, `brigade-org-admin`, `brigade-platform-admin`
- `size` (string): Badge size. Default: `medium`
- `showIcon` (boolean): Show role icon. Default: true
- `className` (string): Additional CSS classes

**Examples:**

```jsx
// Basic usage
<RoleBadge role="brigade-builder" />

// Large badge with icon
<RoleBadge role="brigade-org-admin" size="large" />

// Small badge without icon
<RoleBadge role="brigade-user" size="small" showIcon={false} />
```

### 5. UpgradePrompt

Displays an upgrade prompt when user lacks required permissions.

**Props:**
- `feature` (string): Feature name that requires upgrade
- `requiredTier` (string): Required subscription tier
- `requiredRole` (string): Required user role
- `inline` (boolean): Show as inline banner. Default: false (modal)
- `isOpen` (boolean): Whether modal is open. Default: true
- `onClose` (function): Callback when modal is closed
- `className` (string): Additional CSS classes

**Examples:**

```jsx
// Inline banner
<UpgradePrompt feature="create_agents" inline />

// Modal with state management
const [showUpgrade, setShowUpgrade] = useState(false);

<UpgradePrompt
  feature="publish_agents"
  requiredTier="professional"
  isOpen={showUpgrade}
  onClose={() => setShowUpgrade(false)}
/>

// With specific requirements
<UpgradePrompt
  feature="team_management"
  requiredTier="enterprise"
  requiredRole="brigade-org-admin"
  inline
/>
```

### 6. UserProfile

Displays user profile information with dropdown menu.

**Props:**
- `onLogout` (function): Custom logout handler
- `showBilling` (boolean): Show billing dashboard option. Default: true
- `className` (string): Additional CSS classes

**Features:**
- User avatar with initials
- Username and email display
- Tier and role badges
- Dropdown menu with:
  - Profile settings
  - Billing dashboard (if professional+ tier)
  - Logout

**Examples:**

```jsx
// Basic usage
<UserProfile />

// Custom logout handler
<UserProfile onLogout={handleCustomLogout} />

// Hide billing option
<UserProfile showBilling={false} />

// With custom styling
<UserProfile className="sticky top-0" />
```

### 7. FeatureLock

Overlays locked content with blur effect and upgrade prompt.

**Props:**
- `feature` (string): Feature name to check permission for (required)
- `requiredTier` (string): Required subscription tier
- `requiredRole` (string): Required user role
- `blurStrength` (string): Blur strength. Default: `medium`
  - `light`, `medium`, `heavy`
- `showAnimation` (boolean): Show unlock animation. Default: true
- `className` (string): Additional CSS classes

**Examples:**

```jsx
// Basic usage
<FeatureLock feature="publish_agents">
  <PublishButton />
</FeatureLock>

// With specific requirements
<FeatureLock
  feature="team_management"
  requiredTier="enterprise"
  requiredRole="brigade-org-admin"
  blurStrength="heavy"
>
  <TeamSettings />
</FeatureLock>

// Without animation
<FeatureLock feature="advanced_features" showAnimation={false}>
  <AdvancedPanel />
</FeatureLock>
```

## Common Patterns

### Combining Components

```jsx
// Show feature with badge and lock
<div>
  <div className="flex items-center gap-2 mb-4">
    <h2>Advanced Agent Builder</h2>
    <TierBadge tier="professional" size="small" />
  </div>

  <FeatureLock feature="advanced_builder" requiredTier="professional">
    <AdvancedBuilderPanel />
  </FeatureLock>
</div>
```

### Navigation with Role Gating

```jsx
// Sidebar navigation
<nav>
  <NavLink to="/agents">My Agents</NavLink>

  <RoleGate minRole="brigade-builder">
    <NavLink to="/create">Create Agent</NavLink>
  </RoleGate>

  <RoleGate minRole="brigade-power-builder">
    <NavLink to="/publish">Publish</NavLink>
  </RoleGate>

  <RoleGate minRole="brigade-org-admin">
    <NavLink to="/team">Team Management</NavLink>
  </RoleGate>
</nav>
```

### Form with Permission Checks

```jsx
// Agent creation form
<form>
  <Input label="Agent Name" required />

  <PermissionGate permission="use_custom_models">
    <ModelSelector />
  </PermissionGate>

  <PermissionGate permission="use_advanced_tools">
    <AdvancedToolSelector />
  </PermissionGate>

  <PermissionGate
    permissions={["create_agents", "publish_agents"]}
    requireAll
  >
    <Checkbox label="Publish to marketplace" />
  </PermissionGate>
</form>
```

### Settings Page with Tier Gates

```jsx
// Settings page
<div>
  <UserProfile />

  <h2>Settings</h2>

  <Section title="Profile">
    <ProfileSettings />
  </Section>

  <PermissionGate permission="view_billing">
    <Section title="Billing">
      <BillingSettings />
    </Section>
  </PermissionGate>

  <RoleGate minRole="brigade-org-admin">
    <Section title="Team Management">
      <TeamSettings />
    </Section>
  </RoleGate>
</div>
```

## Styling

All components use Tailwind CSS for styling and include:
- Responsive design
- Hover effects and transitions
- Loading states
- Error handling
- Accessibility features (ARIA labels, keyboard navigation)

### Customization

You can customize component appearance using the `className` prop:

```jsx
<TierBadge
  tier="professional"
  className="shadow-lg hover:shadow-xl"
/>

<PermissionGate
  permission="feature"
  fallback={<CustomFallback className="my-custom-class" />}
>
  <Content />
</PermissionGate>
```

## Integration with Backend

These components integrate with the Brigade authentication system:

1. **useAuth Hook**: Mock implementation provided for development
   - Located at: `/frontend/src/hooks/useAuth.js`
   - Replace with actual Keycloak integration in production

2. **API Endpoints**: Components fetch upgrade info from:
   - `/api/v1/brigade/upgrade-requirements?feature={feature}`
   - This endpoint will be implemented by Track A (Backend) agent

3. **Ops Center Integration**: Upgrade buttons link to:
   - `https://unicorncommander.ai/plans.html`
   - Configured in each component

## Testing

```jsx
// Example test setup
import { render, screen } from '@testing-library/react';
import { PermissionGate } from '../components/auth';

// Mock useAuth hook
jest.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { permissions: ['create_agents'] },
    hasPermission: (perm) => perm === 'create_agents',
    loading: false
  })
}));

test('renders content when permission granted', () => {
  render(
    <PermissionGate permission="create_agents">
      <div>Protected Content</div>
    </PermissionGate>
  );

  expect(screen.getByText('Protected Content')).toBeInTheDocument();
});
```

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

## Dependencies

- React 18.3+
- Framer Motion 11.2+
- Lucide React 0.378+
- Radix UI Tooltip 1.0.7+
- Tailwind CSS 3.4+

## TODO

- [ ] Replace mock useAuth with Keycloak integration
- [ ] Implement backend API endpoint for upgrade requirements
- [ ] Add analytics tracking for upgrade prompts
- [ ] Add unit tests for all components
- [ ] Add Storybook stories
- [ ] Add accessibility testing

## License

MIT License - Magic Unicorn Unconventional Technology & Stuff Inc

## Support

For issues or questions, contact the Brigade team or open an issue on GitHub.

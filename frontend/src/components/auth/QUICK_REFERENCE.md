# Brigade Auth Components - Quick Reference

⚡ Quick copy-paste reference for common use cases

## Import

```jsx
import {
  PermissionGate,
  RoleGate,
  TierBadge,
  RoleBadge,
  UpgradePrompt,
  UserProfile,
  FeatureLock
} from '../components/auth';
```

## PermissionGate

### Single Permission
```jsx
<PermissionGate permission="create_agents">
  <Button>Create Agent</Button>
</PermissionGate>
```

### Multiple Permissions (OR)
```jsx
<PermissionGate permissions={["view_agents", "edit_agents"]}>
  <AgentList />
</PermissionGate>
```

### Multiple Permissions (AND)
```jsx
<PermissionGate permissions={["create_agents", "publish_agents"]} requireAll>
  <PublishButton />
</PermissionGate>
```

### Custom Fallback
```jsx
<PermissionGate
  permission="advanced_features"
  fallback={<p>Not available</p>}
  showUpgradePrompt={false}
>
  <AdvancedPanel />
</PermissionGate>
```

## RoleGate

### Single Role
```jsx
<RoleGate role="brigade-builder">
  <BuilderTools />
</RoleGate>
```

### Multiple Roles (OR)
```jsx
<RoleGate roles={["brigade-builder", "brigade-power-builder"]}>
  <AdvancedFeatures />
</RoleGate>
```

### Minimum Role (Hierarchical)
```jsx
<RoleGate minRole="brigade-power-builder">
  <PublishToMarketplace />
</RoleGate>
```

## TierBadge

```jsx
<TierBadge tier="professional" />
<TierBadge tier="enterprise" size="large" />
<TierBadge tier="starter" size="small" showIcon={false} />
```

**Tiers**: `trial`, `starter`, `professional`, `enterprise`, `founders`
**Sizes**: `small`, `medium`, `large`

## RoleBadge

```jsx
<RoleBadge role="brigade-builder" />
<RoleBadge role="brigade-org-admin" size="large" />
<RoleBadge role="brigade-user" size="small" showIcon={false} />
```

**Roles**:
- `brigade-user`
- `brigade-builder`
- `brigade-power-builder`
- `brigade-org-admin`
- `brigade-platform-admin`

## UpgradePrompt

### Inline Banner
```jsx
<UpgradePrompt feature="create_agents" inline />
```

### Modal with State
```jsx
const [showUpgrade, setShowUpgrade] = useState(false);

<UpgradePrompt
  feature="publish_agents"
  requiredTier="professional"
  isOpen={showUpgrade}
  onClose={() => setShowUpgrade(false)}
/>
```

### With Specific Requirements
```jsx
<UpgradePrompt
  feature="team_management"
  requiredTier="enterprise"
  requiredRole="brigade-org-admin"
  inline
/>
```

## UserProfile

```jsx
<UserProfile />
<UserProfile onLogout={handleLogout} />
<UserProfile showBilling={false} />
<UserProfile className="sticky top-0" />
```

## FeatureLock

### Basic Usage
```jsx
<FeatureLock feature="publish_agents">
  <PublishButton />
</FeatureLock>
```

### With Requirements
```jsx
<FeatureLock
  feature="team_management"
  requiredTier="enterprise"
  requiredRole="brigade-org-admin"
  blurStrength="heavy"
>
  <TeamSettings />
</FeatureLock>
```

**Blur Strengths**: `light`, `medium`, `heavy`

## Common Patterns

### Navigation Menu
```jsx
<nav>
  <NavLink to="/">Dashboard</NavLink>

  <RoleGate minRole="brigade-builder">
    <NavLink to="/create">Create Agent</NavLink>
  </RoleGate>

  <RoleGate minRole="brigade-power-builder">
    <NavLink to="/publish">Publish</NavLink>
  </RoleGate>

  <RoleGate minRole="brigade-org-admin">
    <NavLink to="/team">Team</NavLink>
  </RoleGate>
</nav>
```

### Settings Page
```jsx
<div>
  <UserProfile />

  <Section title="Profile">
    <ProfileSettings />
  </Section>

  <PermissionGate permission="view_billing">
    <Section title="Billing">
      <BillingSettings />
    </Section>
  </PermissionGate>

  <RoleGate minRole="brigade-org-admin">
    <Section title="Team">
      <TeamSettings />
    </Section>
  </RoleGate>
</div>
```

### Feature with Badge
```jsx
<div>
  <div className="flex items-center gap-2">
    <h2>Advanced Features</h2>
    <TierBadge tier="professional" size="small" />
  </div>

  <FeatureLock feature="advanced_features" requiredTier="professional">
    <AdvancedPanel />
  </FeatureLock>
</div>
```

### Form with Conditional Fields
```jsx
<form>
  <Input label="Name" required />

  <PermissionGate permission="use_custom_models">
    <ModelSelector />
  </PermissionGate>

  <PermissionGate permission="use_advanced_tools">
    <ToolSelector />
  </PermissionGate>

  <PermissionGate permissions={["create_agents", "publish_agents"]} requireAll>
    <Checkbox label="Publish to marketplace" />
  </PermissionGate>
</form>
```

## useAuth Hook

```jsx
import useAuth from '../../hooks/useAuth';

const MyComponent = () => {
  const {
    user,                          // Current user object
    isAuthenticated,               // Boolean
    isLoading,                     // Boolean
    hasPermission,                 // Function (permission: string) => boolean
    hasRole,                       // Function (role: string) => boolean
    hasTier,                       // Function (tier: string) => boolean
    canUseTool,                    // Function (tool: string) => Promise<boolean>
    getUpgradeInfo,                // Function (feature: string) => Promise<Object>
    login,                         // Function () => Promise<void>
    logout                         // Function () => Promise<void>
  } = useAuth();

  return (
    <div>
      {user && <p>Hello, {user.name}</p>}

      {hasPermission('create_agents') && (
        <Button>Create Agent</Button>
      )}
    </div>
  );
};
```

## Tier Hierarchy (Lowest to Highest)

1. `trial` - $1/week - 100 API calls/day
2. `starter` - $19/month - 1,000 API calls/month
3. `professional` - $49/month - 10,000 API calls/month
4. `enterprise` - $99/month - Unlimited
5. `founders` - Special - Lifetime access

## Role Hierarchy (Lowest to Highest)

1. `brigade-user` - View public agents
2. `brigade-builder` - Create agents
3. `brigade-power-builder` - Publish agents
4. `brigade-org-admin` - Manage team
5. `brigade-platform-admin` - Full admin

## Permission Examples

Common permissions:
- `view_agents` - View agent list
- `create_agents` - Create new agents
- `edit_agents` - Edit own agents
- `publish_agents` - Publish to marketplace
- `use_tools` - Use agent tools
- `create_api_keys` - Generate API keys
- `view_billing` - View billing dashboard
- `manage_team` - Manage team members

## Styling

All components use Tailwind CSS. Customize with `className`:

```jsx
<TierBadge tier="professional" className="shadow-lg hover:shadow-xl" />
```

## Ops Center Links

Upgrade buttons link to:
- Plans: `https://unicorncommander.ai/plans.html`
- Billing: `https://unicorncommander.ai/billing-settings.html`

## Troubleshooting

**Components not rendering?**
- Check if `useAuth()` is returning user data
- Verify permissions array in user object

**Tooltips not showing?**
- Ensure `@radix-ui/react-tooltip` is installed
- Check z-index conflicts

**Animations not working?**
- Verify `framer-motion` is installed
- Check Tailwind JIT mode is enabled

---

For full documentation, see `README.md` and `EXAMPLES.md`

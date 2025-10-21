# Brigade Auth Components - Usage Examples

Real-world usage examples for the Brigade authentication component library.

## Table of Contents

1. [Agent Builder Page](#agent-builder-page)
2. [Marketplace Page](#marketplace-page)
3. [Settings Page](#settings-page)
4. [Navigation](#navigation)
5. [Team Management](#team-management)
6. [API Keys Management](#api-keys-management)
7. [Billing Integration](#billing-integration)

---

## Agent Builder Page

Complete example of an agent builder with permission gating:

```jsx
import React, { useState } from 'react';
import {
  PermissionGate,
  RoleGate,
  FeatureLock,
  TierBadge
} from '../components/auth';

const AgentBuilderPage = () => {
  const [agentConfig, setAgentConfig] = useState({
    name: '',
    description: '',
    model: 'gpt-4',
    tools: [],
    publishToMarketplace: false
  });

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Page Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-3xl font-bold">Create Agent</h1>
          <RoleGate minRole="brigade-builder">
            <TierBadge tier="professional" size="small" />
          </RoleGate>
        </div>
        <p className="text-gray-600">
          Build your custom AI agent with advanced tools and configurations
        </p>
      </div>

      {/* Basic Configuration - Available to all */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-4">Basic Configuration</h2>
        <div className="space-y-4">
          <input
            type="text"
            placeholder="Agent Name"
            value={agentConfig.name}
            onChange={(e) => setAgentConfig({ ...agentConfig, name: e.target.value })}
            className="w-full px-4 py-2 border rounded-lg"
          />
          <textarea
            placeholder="Agent Description"
            value={agentConfig.description}
            onChange={(e) => setAgentConfig({ ...agentConfig, description: e.target.value })}
            className="w-full px-4 py-2 border rounded-lg h-24"
          />
        </div>
      </section>

      {/* Advanced Model Selection - Requires Permission */}
      <PermissionGate permission="use_custom_models">
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Model Selection</h2>
          <select
            value={agentConfig.model}
            onChange={(e) => setAgentConfig({ ...agentConfig, model: e.target.value })}
            className="w-full px-4 py-2 border rounded-lg"
          >
            <option value="gpt-4">GPT-4</option>
            <option value="gpt-4-turbo">GPT-4 Turbo</option>
            <option value="claude-3-opus">Claude 3 Opus</option>
            <option value="claude-3-sonnet">Claude 3 Sonnet</option>
          </select>
        </section>
      </PermissionGate>

      {/* Advanced Tools - Locked Feature */}
      <FeatureLock
        feature="use_advanced_tools"
        requiredTier="professional"
        blurStrength="medium"
      >
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Advanced Tools</h2>
          <div className="grid grid-cols-2 gap-4">
            <ToolCard name="Web Search" icon="🔍" />
            <ToolCard name="Code Execution" icon="💻" />
            <ToolCard name="Image Analysis" icon="🖼️" />
            <ToolCard name="File Processing" icon="📁" />
          </div>
        </section>
      </FeatureLock>

      {/* Publishing Options - Power Builder Only */}
      <RoleGate minRole="brigade-power-builder">
        <section className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-xl font-semibold">Publishing</h2>
            <RoleBadge role="brigade-power-builder" size="small" />
          </div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={agentConfig.publishToMarketplace}
              onChange={(e) => setAgentConfig({
                ...agentConfig,
                publishToMarketplace: e.target.checked
              })}
            />
            <span>Publish to Agent Marketplace</span>
          </label>
        </section>
      </RoleGate>

      {/* Action Buttons */}
      <div className="flex gap-4">
        <PermissionGate permission="create_agents">
          <button className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
            Create Agent
          </button>
        </PermissionGate>

        <button className="px-6 py-3 border border-gray-300 rounded-lg hover:bg-gray-50">
          Cancel
        </button>
      </div>
    </div>
  );
};

const ToolCard = ({ name, icon }) => (
  <div className="p-4 border rounded-lg hover:border-purple-400 cursor-pointer">
    <div className="text-3xl mb-2">{icon}</div>
    <p className="font-medium">{name}</p>
  </div>
);

export default AgentBuilderPage;
```

---

## Marketplace Page

Agent marketplace with tier-based filtering:

```jsx
import React, { useState } from 'react';
import {
  PermissionGate,
  RoleGate,
  TierBadge,
  UpgradePrompt
} from '../components/auth';

const MarketplacePage = () => {
  const [showUpgrade, setShowUpgrade] = useState(false);

  const agents = [
    { id: 1, name: 'Research Assistant', tier: 'starter', downloads: 1200 },
    { id: 2, name: 'Code Reviewer', tier: 'professional', downloads: 850 },
    { id: 3, name: 'Data Analyst', tier: 'professional', downloads: 620 },
    { id: 4, name: 'Enterprise Bot', tier: 'enterprise', downloads: 340 }
  ];

  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-8">Agent Marketplace</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {agents.map(agent => (
          <AgentCard
            key={agent.id}
            agent={agent}
            onUpgradeRequired={() => setShowUpgrade(true)}
          />
        ))}
      </div>

      {/* Publishing Section - Power Builder Only */}
      <RoleGate minRole="brigade-power-builder">
        <div className="mt-12 p-6 bg-purple-50 rounded-lg border border-purple-200">
          <h2 className="text-xl font-semibold mb-4">Publish Your Agent</h2>
          <p className="text-gray-600 mb-4">
            Share your custom agents with the Brigade community
          </p>
          <button className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
            Publish Agent
          </button>
        </div>
      </RoleGate>

      {/* Upgrade Modal */}
      <UpgradePrompt
        feature="download_premium_agents"
        requiredTier="professional"
        isOpen={showUpgrade}
        onClose={() => setShowUpgrade(false)}
      />
    </div>
  );
};

const AgentCard = ({ agent, onUpgradeRequired }) => {
  const { hasMinTier } = useAuth();

  const handleDownload = () => {
    if (!hasMinTier(agent.tier)) {
      onUpgradeRequired();
      return;
    }
    // Download agent
    console.log('Downloading:', agent.name);
  };

  return (
    <div className="border rounded-lg p-6 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-lg font-semibold">{agent.name}</h3>
        <TierBadge tier={agent.tier} size="small" />
      </div>

      <p className="text-gray-600 text-sm mb-4">
        {agent.downloads.toLocaleString()} downloads
      </p>

      <PermissionGate
        permission="download_agents"
        fallback={
          <button
            onClick={onUpgradeRequired}
            className="w-full px-4 py-2 bg-gray-200 text-gray-600 rounded-lg"
          >
            Upgrade to Download
          </button>
        }
      >
        <button
          onClick={handleDownload}
          className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
        >
          Download Agent
        </button>
      </PermissionGate>
    </div>
  );
};

export default MarketplacePage;
```

---

## Settings Page

Complete settings page with billing integration:

```jsx
import React from 'react';
import {
  UserProfile,
  PermissionGate,
  RoleGate,
  TierBadge,
  RoleBadge
} from '../components/auth';
import { useAuth } from '../../hooks/useAuth';

const SettingsPage = () => {
  const { user } = useAuth();

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-8">Settings</h1>

      {/* User Profile Section */}
      <section className="mb-8 p-6 bg-white border rounded-lg">
        <h2 className="text-xl font-semibold mb-4">Profile</h2>
        <UserProfile />
      </section>

      {/* Account Information */}
      <section className="mb-8 p-6 bg-white border rounded-lg">
        <h2 className="text-xl font-semibold mb-4">Account Information</h2>
        <div className="space-y-4">
          <div>
            <label className="text-sm text-gray-600">Email</label>
            <p className="font-medium">{user?.email}</p>
          </div>

          <div>
            <label className="text-sm text-gray-600">Subscription</label>
            <div className="mt-1">
              <TierBadge tier={user?.tier} />
            </div>
          </div>

          <div>
            <label className="text-sm text-gray-600">Role</label>
            <div className="mt-1">
              <RoleBadge role={user?.role} />
            </div>
          </div>
        </div>
      </section>

      {/* Billing Section - Professional+ Only */}
      <PermissionGate permission="view_billing">
        <section className="mb-8 p-6 bg-white border rounded-lg">
          <h2 className="text-xl font-semibold mb-4">Billing</h2>
          <div className="space-y-4">
            <button
              onClick={() => window.open('https://unicorncommander.ai/billing-settings.html', '_blank')}
              className="w-full px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
            >
              Manage Billing
            </button>

            <button className="w-full px-4 py-3 border border-gray-300 rounded-lg hover:bg-gray-50">
              View Invoices
            </button>
          </div>
        </section>
      </PermissionGate>

      {/* Team Management - Org Admin Only */}
      <RoleGate minRole="brigade-org-admin">
        <section className="mb-8 p-6 bg-white border rounded-lg">
          <h2 className="text-xl font-semibold mb-4">Team Management</h2>
          <div className="space-y-4">
            <button className="w-full px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
              Manage Team Members
            </button>

            <button className="w-full px-4 py-3 border border-gray-300 rounded-lg hover:bg-gray-50">
              Organization Settings
            </button>
          </div>
        </section>
      </RoleGate>

      {/* Platform Admin - Platform Admin Only */}
      <RoleGate role="brigade-platform-admin">
        <section className="mb-8 p-6 bg-red-50 border border-red-200 rounded-lg">
          <h2 className="text-xl font-semibold mb-4 text-red-700">
            Platform Administration
          </h2>
          <div className="space-y-4">
            <button className="w-full px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700">
              System Configuration
            </button>

            <button className="w-full px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700">
              Manage All Users
            </button>
          </div>
        </section>
      </RoleGate>
    </div>
  );
};

export default SettingsPage;
```

---

## Navigation

Sidebar navigation with role-based menu items:

```jsx
import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  UserProfile,
  RoleGate,
  PermissionGate,
  TierBadge
} from '../components/auth';
import {
  Home,
  Cpu,
  Store,
  Settings,
  Users,
  Shield,
  Key
} from 'lucide-react';

const Sidebar = () => {
  return (
    <div className="w-64 h-screen bg-white border-r flex flex-col">
      {/* User Profile */}
      <div className="p-4 border-b">
        <UserProfile />
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
        {/* Always visible */}
        <NavItem to="/" icon={Home} label="Dashboard" />

        {/* Builder+ */}
        <RoleGate minRole="brigade-builder">
          <NavItem to="/agents" icon={Cpu} label="My Agents" />
          <NavItem to="/create" icon={Cpu} label="Create Agent" />
        </RoleGate>

        {/* Power Builder+ */}
        <RoleGate minRole="brigade-power-builder">
          <NavItem to="/marketplace" icon={Store} label="Marketplace" />
        </RoleGate>

        {/* API Keys */}
        <PermissionGate permission="create_api_keys">
          <NavItem to="/api-keys" icon={Key} label="API Keys" />
        </PermissionGate>

        {/* Org Admin+ */}
        <RoleGate minRole="brigade-org-admin">
          <NavItem to="/team" icon={Users} label="Team" />
        </RoleGate>

        {/* Platform Admin */}
        <RoleGate role="brigade-platform-admin">
          <NavItem to="/admin" icon={Shield} label="Platform Admin" />
        </RoleGate>

        {/* Always visible */}
        <NavItem to="/settings" icon={Settings} label="Settings" />
      </nav>

      {/* Upgrade CTA */}
      <PermissionGate
        permission="upgrade_available"
        fallback={null}
        showUpgradePrompt={false}
      >
        <div className="p-4 border-t">
          <div className="bg-gradient-to-r from-purple-600 to-pink-600 text-white p-4 rounded-lg">
            <p className="font-semibold mb-2">Upgrade to Pro</p>
            <p className="text-sm mb-3 text-purple-100">
              Unlock all features
            </p>
            <button className="w-full px-4 py-2 bg-white text-purple-600 rounded-lg hover:bg-gray-100">
              Upgrade Now
            </button>
          </div>
        </div>
      </PermissionGate>
    </div>
  );
};

const NavItem = ({ to, icon: Icon, label }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `flex items-center gap-3 px-4 py-2 rounded-lg transition-colors ${
        isActive
          ? 'bg-purple-100 text-purple-700'
          : 'text-gray-700 hover:bg-gray-100'
      }`
    }
  >
    <Icon size={20} />
    <span>{label}</span>
  </NavLink>
);

export default Sidebar;
```

---

## Team Management

Enterprise team management page:

```jsx
import React, { useState } from 'react';
import {
  RoleGate,
  TierBadge,
  RoleBadge,
  UpgradePrompt
} from '../components/auth';

const TeamManagementPage = () => {
  const [showUpgrade, setShowUpgrade] = useState(false);

  const teamMembers = [
    { id: 1, name: 'John Doe', email: 'john@example.com', role: 'brigade-builder' },
    { id: 2, name: 'Jane Smith', email: 'jane@example.com', role: 'brigade-power-builder' },
    { id: 3, name: 'Bob Johnson', email: 'bob@example.com', role: 'brigade-org-admin' }
  ];

  return (
    <RoleGate
      minRole="brigade-org-admin"
      fallback={
        <div className="max-w-4xl mx-auto p-6">
          <UpgradePrompt
            feature="team_management"
            requiredTier="enterprise"
            requiredRole="brigade-org-admin"
            inline
          />
        </div>
      }
    >
      <div className="max-w-4xl mx-auto p-6">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">Team Management</h1>
          <TierBadge tier="enterprise" />
        </div>

        {/* Team Members */}
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Email
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Role
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {teamMembers.map(member => (
                <tr key={member.id}>
                  <td className="px-6 py-4 whitespace-nowrap">{member.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-600">
                    {member.email}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <RoleBadge role={member.role} size="small" />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button className="text-purple-600 hover:text-purple-700 mr-4">
                      Edit
                    </button>
                    <button className="text-red-600 hover:text-red-700">
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Add Member Button */}
        <div className="mt-6">
          <button className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
            Invite Team Member
          </button>
        </div>
      </div>
    </RoleGate>
  );
};

export default TeamManagementPage;
```

---

## API Keys Management

API key management with permission checks:

```jsx
import React, { useState } from 'react';
import {
  PermissionGate,
  TierBadge,
  UpgradePrompt
} from '../components/auth';
import { Key, Copy, Trash2 } from 'lucide-react';

const APIKeysPage = () => {
  const [apiKeys, setApiKeys] = useState([
    { id: 1, name: 'Production Key', key: 'brig_prod_****', created: '2025-10-01' },
    { id: 2, name: 'Development Key', key: 'brig_dev_****', created: '2025-10-05' }
  ]);

  return (
    <PermissionGate
      permission="create_api_keys"
      fallback={
        <div className="max-w-4xl mx-auto p-6">
          <UpgradePrompt
            feature="create_api_keys"
            requiredTier="professional"
            inline
          />
        </div>
      }
    >
      <div className="max-w-4xl mx-auto p-6">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">API Keys</h1>
            <p className="text-gray-600 mt-2">
              Manage your Brigade API keys for programmatic access
            </p>
          </div>
          <TierBadge tier="professional" />
        </div>

        {/* API Keys List */}
        <div className="space-y-4 mb-6">
          {apiKeys.map(key => (
            <div
              key={key.id}
              className="flex items-center justify-between p-4 bg-white border rounded-lg"
            >
              <div className="flex items-center gap-4">
                <Key size={24} className="text-purple-600" />
                <div>
                  <p className="font-medium">{key.name}</p>
                  <p className="text-sm text-gray-600">{key.key}</p>
                  <p className="text-xs text-gray-400">Created: {key.created}</p>
                </div>
              </div>

              <div className="flex gap-2">
                <button className="p-2 text-gray-600 hover:text-gray-800">
                  <Copy size={18} />
                </button>
                <button className="p-2 text-red-600 hover:text-red-700">
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Create New Key */}
        <button className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
          Create New API Key
        </button>

        {/* Usage Information */}
        <div className="mt-8 p-6 bg-purple-50 border border-purple-200 rounded-lg">
          <h3 className="font-semibold mb-2">Usage Example</h3>
          <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm">
{`import requests

url = "https://api.brigade.ai/v1/agents"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)
print(response.json())`}
          </pre>
        </div>
      </div>
    </PermissionGate>
  );
};

export default APIKeysPage;
```

---

## Billing Integration

Billing dashboard integration:

```jsx
import React, { useState, useEffect } from 'react';
import {
  PermissionGate,
  TierBadge,
  UpgradePrompt
} from '../components/auth';
import { useAuth } from '../../hooks/useAuth';
import { CreditCard, Receipt, TrendingUp } from 'lucide-react';

const BillingPage = () => {
  const { user } = useAuth();
  const [usage, setUsage] = useState({
    apiCalls: 4230,
    limit: 10000,
    period: 'October 2025'
  });

  return (
    <PermissionGate
      permission="view_billing"
      fallback={
        <div className="max-w-4xl mx-auto p-6">
          <UpgradePrompt
            feature="view_billing"
            requiredTier="professional"
            inline
          />
        </div>
      }
    >
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-8">Billing & Usage</h1>

        {/* Current Plan */}
        <div className="bg-white border rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Current Plan</h2>
          <div className="flex items-center justify-between">
            <div>
              <TierBadge tier={user?.tier} size="large" />
              <p className="text-gray-600 mt-2">
                {user?.tier === 'professional' && '$49/month'}
                {user?.tier === 'enterprise' && '$99/month'}
              </p>
            </div>
            <button className="px-6 py-3 border border-gray-300 rounded-lg hover:bg-gray-50">
              Change Plan
            </button>
          </div>
        </div>

        {/* Usage Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <StatCard
            icon={TrendingUp}
            label="API Calls"
            value={`${usage.apiCalls.toLocaleString()} / ${usage.limit.toLocaleString()}`}
            percentage={(usage.apiCalls / usage.limit) * 100}
          />
          <StatCard
            icon={CreditCard}
            label="Billing Period"
            value={usage.period}
          />
          <StatCard
            icon={Receipt}
            label="Next Invoice"
            value="Nov 1, 2025"
          />
        </div>

        {/* Payment Method */}
        <div className="bg-white border rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Payment Method</h2>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <CreditCard size={24} />
              <div>
                <p className="font-medium">•••• •••• •••• 4242</p>
                <p className="text-sm text-gray-600">Expires 12/2025</p>
              </div>
            </div>
            <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
              Update
            </button>
          </div>
        </div>

        {/* Manage in Ops Center */}
        <button
          onClick={() => window.open('https://unicorncommander.ai/billing-settings.html', '_blank')}
          className="w-full px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
        >
          Manage Billing in Ops Center
        </button>
      </div>
    </PermissionGate>
  );
};

const StatCard = ({ icon: Icon, label, value, percentage }) => (
  <div className="bg-white border rounded-lg p-6">
    <div className="flex items-center gap-2 mb-2">
      <Icon size={20} className="text-purple-600" />
      <p className="text-sm text-gray-600">{label}</p>
    </div>
    <p className="text-2xl font-bold">{value}</p>
    {percentage !== undefined && (
      <div className="mt-2 bg-gray-200 rounded-full h-2">
        <div
          className="bg-purple-600 h-2 rounded-full"
          style={{ width: `${percentage}%` }}
        />
      </div>
    )}
  </div>
);

export default BillingPage;
```

---

These examples demonstrate real-world usage of all Brigade auth components in typical application scenarios. Each example is production-ready and follows React best practices.

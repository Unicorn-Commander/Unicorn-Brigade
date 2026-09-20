# Executed by Grok (headless lane)
"""
Tests for New Agent Configurations

Tests coverage for:
- 13 production agents from seed_agents.json
- Agent structure and field validation
- Tool assignments
- System prompts and personas
- Phase 1 agents (sql-analyst, support-agent, code-reviewer)
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def seed_agents():
    """Load seed agents from JSON file"""
    seed_file = Path(__file__).parent.parent / "app" / "data" / "seed_agents.json"
    with open(seed_file) as f:
        return json.load(f)


class TestAgentCount:
    """Test agent counts and presence"""

    def test_total_agent_count(self, seed_agents):
        """Sanity check on the seeded agent count.

        We don't pin to an exact number — the seed file grows naturally as
        new specialized agents land. Instead we enforce a floor (the count
        when this test was last reviewed) so a sudden truncation of
        seed_agents.json fails fast.
        """
        assert len(seed_agents) >= 13, (
            f"Expected at least 13 seeded agents, got {len(seed_agents)}"
        )

    def test_all_agents_have_unique_ids(self, seed_agents):
        """Verify all agents have unique IDs"""
        ids = [agent['id'] for agent in seed_agents]
        assert len(ids) == len(set(ids)), "Agent IDs must be unique"

    def test_all_agents_have_unique_names(self, seed_agents):
        """Verify all agents have unique names"""
        names = [agent['name'] for agent in seed_agents]
        assert len(names) == len(set(names)), "Agent names must be unique"


class TestAgentStructure:
    """Test agent JSON structure and required fields"""

    @pytest.mark.parametrize("required_field", [
        "id", "name", "displayName", "title", "rank", "avatar",
        "bio", "persona", "systemPrompt", "domain", "subdomain",
        "status", "type", "agentType", "capabilities", "model",
        "temperature", "maxTokens", "tools", "createdAt"
    ])
    def test_agents_have_required_fields(self, seed_agents, required_field):
        """Test that all agents have required fields"""
        for agent in seed_agents:
            assert required_field in agent, \
                f"Agent {agent.get('id', 'unknown')} missing required field: {required_field}"

    def test_agents_have_non_empty_system_prompts(self, seed_agents):
        """Verify all agents have non-empty system prompts"""
        for agent in seed_agents:
            assert agent['systemPrompt'], \
                f"Agent {agent['id']} has empty systemPrompt"
            assert len(agent['systemPrompt']) > 50, \
                f"Agent {agent['id']} systemPrompt too short (< 50 chars)"

    def test_agents_have_non_empty_personas(self, seed_agents):
        """Verify all agents have non-empty personas"""
        for agent in seed_agents:
            assert agent['persona'], \
                f"Agent {agent['id']} has empty persona"
            assert len(agent['persona']) > 20, \
                f"Agent {agent['id']} persona too short (< 20 chars)"

    def test_agents_have_capabilities(self, seed_agents):
        """Verify all agents have at least one capability"""
        for agent in seed_agents:
            assert isinstance(agent['capabilities'], list), \
                f"Agent {agent['id']} capabilities must be a list"
            assert len(agent['capabilities']) > 0, \
                f"Agent {agent['id']} has no capabilities"

    def test_agents_have_tools(self, seed_agents):
        """Verify all agents have at least one tool"""
        for agent in seed_agents:
            assert isinstance(agent['tools'], list), \
                f"Agent {agent['id']} tools must be a list"
            assert len(agent['tools']) > 0, \
                f"Agent {agent['id']} has no tools assigned"

    def test_agent_temperature_range(self, seed_agents):
        """Verify agent temperature is in valid range [0, 1]"""
        for agent in seed_agents:
            temp = agent['temperature']
            assert 0 <= temp <= 1, \
                f"Agent {agent['id']} temperature {temp} out of range [0, 1]"

    def test_agent_max_tokens_positive(self, seed_agents):
        """Verify agent maxTokens is positive"""
        for agent in seed_agents:
            max_tokens = agent['maxTokens']
            assert max_tokens > 0, \
                f"Agent {agent['id']} maxTokens must be positive"
            assert max_tokens <= 16000, \
                f"Agent {agent['id']} maxTokens {max_tokens} unusually high"


class TestCoreAgents:
    """Test core orchestration and builder agents"""

    def test_the_general_exists(self, seed_agents):
        """Verify The General orchestrator exists"""
        general = next((a for a in seed_agents if a['id'] == 'the-general'), None)
        assert general is not None, "The General agent must exist"
        assert general['type'] == 'orchestrator'
        assert general['domain'] == 'orchestration'

    def test_gunny_exists(self, seed_agents):
        """Verify Gunny agent builder exists"""
        gunny = next((a for a in seed_agents if a['id'] == 'gunny'), None)
        assert gunny is not None, "Gunny agent must exist"
        assert gunny['domain'] == 'meta'
        assert gunny['subdomain'] == 'builder'


class TestPhase1Agents:
    """Test Phase 1 specialized agents"""

    def test_sql_analyst_exists(self, seed_agents):
        """Verify SQL Analyst agent exists with correct configuration"""
        sql_analyst = next((a for a in seed_agents if a['id'] == 'sql-analyst'), None)
        assert sql_analyst is not None, "SQL Analyst must exist"

        # Check required fields
        assert sql_analyst['displayName'] == 'SQL Analyst'
        assert sql_analyst['domain'] == 'data'
        assert sql_analyst['subdomain'] == 'database'

        # Check capabilities
        assert 'text-to-sql' in sql_analyst['capabilities']
        assert 'query-optimization' in sql_analyst['capabilities']
        assert 'database-analysis' in sql_analyst['capabilities']

        # Check tools
        assert 'database' in sql_analyst['tools']
        assert 'calculator' in sql_analyst['tools']

        # Check system prompt mentions text-to-SQL
        assert 'text-to-sql' in sql_analyst['systemPrompt'].lower() or 'sql' in sql_analyst['systemPrompt'].lower()

    def test_support_agent_exists(self, seed_agents):
        """Verify Support Agent exists with correct configuration"""
        support = next((a for a in seed_agents if a['id'] == 'support-agent'), None)
        assert support is not None, "Support Agent must exist"

        # Check required fields
        assert support['displayName'] == 'Support Specialist'
        assert support['domain'] == 'support'
        assert support['subdomain'] == 'customer-service'

        # Check capabilities
        assert 'customer-support' in support['capabilities']
        assert 'faq-search' in support['capabilities'] or 'escalation' in support['capabilities']

        # Check tools
        assert 'memory' in support['tools']
        assert 'email' in support['tools'] or 'web_search' in support['tools']

    def test_code_reviewer_exists(self, seed_agents):
        """Verify Code Reviewer agent exists with correct configuration"""
        reviewer = next((a for a in seed_agents if a['id'] == 'code-reviewer'), None)
        assert reviewer is not None, "Code Reviewer must exist"

        # Check required fields
        assert reviewer['displayName'] == 'Code Reviewer'
        assert reviewer['domain'] == 'engineering'
        assert reviewer['subdomain'] == 'code-review'

        # Check capabilities
        assert 'code-review' in reviewer['capabilities']
        assert 'security-scan' in reviewer['capabilities'] or 'bug-detection' in reviewer['capabilities']

        # Check tools
        assert 'http_request' in reviewer['tools'] or 'shell' in reviewer['tools']


class TestDomainAgents:
    """Test domain-specific specialist agents"""

    def test_technology_domain_agents(self, seed_agents):
        """Verify technology domain agents exist"""
        tech_agents = [a for a in seed_agents if a['domain'] == 'technology']
        assert len(tech_agents) >= 3, "Should have multiple technology agents"

        # Check for key technology agents
        agent_ids = [a['id'] for a in tech_agents]
        assert 'sgt-cipher' in agent_ids  # Cybersecurity
        assert 'cpt-fullstack' in agent_ids  # Full-stack engineering
        assert 'maj-devops' in agent_ids  # DevOps

    def test_financial_domain_agents(self, seed_agents):
        """Verify financial domain agents exist"""
        finance_agents = [a for a in seed_agents if a['domain'] == 'financial']
        assert len(finance_agents) >= 2, "Should have financial agents"

        agent_ids = [a['id'] for a in finance_agents]
        assert 'col-finance' in agent_ids
        assert 'lt-taxstrat' in agent_ids

    def test_legal_domain_agents(self, seed_agents):
        """Verify legal domain agents exist"""
        legal_agents = [a for a in seed_agents if a['domain'] == 'legal']
        assert len(legal_agents) >= 1, "Should have legal agents"

        agent_ids = [a['id'] for a in legal_agents]
        assert 'judge-advocate' in agent_ids

    def test_medical_domain_agents(self, seed_agents):
        """Verify medical domain agents exist"""
        medical_agents = [a for a in seed_agents if a['domain'] == 'medical']
        assert len(medical_agents) >= 1, "Should have medical agents"

        agent_ids = [a['id'] for a in medical_agents]
        assert 'doc-medresearch' in agent_ids

    def test_investigation_domain_agents(self, seed_agents):
        """Verify investigation domain agents exist"""
        investigation_agents = [a for a in seed_agents if a['domain'] == 'investigation']
        assert len(investigation_agents) >= 1, "Should have investigation agents"

        agent_ids = [a['id'] for a in investigation_agents]
        assert 'detective-holmes' in agent_ids

    def test_intelligence_domain_agents(self, seed_agents):
        """Verify intelligence domain agents exist"""
        intel_agents = [a for a in seed_agents if a['domain'] == 'intelligence']
        assert len(intel_agents) >= 1, "Should have intelligence agents"

        agent_ids = [a['id'] for a in intel_agents]
        assert 'prof-datasci' in agent_ids


class TestAgentTypes:
    """Test agent type classifications"""

    def test_agent_types_valid(self, seed_agents):
        """Verify all agents have valid agent types"""
        valid_types = ['research', 'code', 'analysis']

        for agent in seed_agents:
            assert agent['agentType'] in valid_types, \
                f"Agent {agent['id']} has invalid agentType: {agent['agentType']}"

    def test_has_research_agents(self, seed_agents):
        """Verify we have research-type agents"""
        research_agents = [a for a in seed_agents if a['agentType'] == 'research']
        assert len(research_agents) > 0, "Should have research agents"

    def test_has_code_agents(self, seed_agents):
        """Verify we have code-type agents"""
        code_agents = [a for a in seed_agents if a['agentType'] == 'code']
        assert len(code_agents) > 0, "Should have code agents"

    def test_has_analysis_agents(self, seed_agents):
        """Verify we have analysis-type agents"""
        analysis_agents = [a for a in seed_agents if a['agentType'] == 'analysis']
        assert len(analysis_agents) > 0, "Should have analysis agents"


class TestAgentModels:
    """Test agent LLM model configurations"""

    def test_valid_model_formats(self, seed_agents):
        """Verify seeded agents use the production model IDs.

        claude-sonnet-4 from 66f8d81; 11 agents repointed to qwen3.6-35b-a3b
        in 40c0c28963d4c29372127ff1a1b1f4df298d182d.
        """
        expected_seed_models = {
            "the-general": "claude-sonnet-4",
            "gunny": "claude-sonnet-4",
            "sgt-cipher": "qwen3.6-35b-a3b",
            "cpt-fullstack": "qwen3.6-35b-a3b",
            "maj-devops": "qwen3.6-35b-a3b",
            "col-finance": "claude-sonnet-4",
            "lt-taxstrat": "qwen3.6-35b-a3b",
            "judge-advocate": "claude-sonnet-4",
            "doc-medresearch": "claude-sonnet-4",
            "detective-holmes": "claude-sonnet-4",
            "prof-datasci": "qwen3.6-35b-a3b",
            "support-agent": "qwen3.6-35b-a3b",
            "code-reviewer": "qwen3.6-35b-a3b",
            "sql-analyst": "qwen3.6-35b-a3b",
            "sgt-scribe": "qwen3.6-35b-a3b",
            "maj-leadgen": "qwen3.6-35b-a3b",
            "lt-docanalyst": "qwen3.6-35b-a3b",
        }
        actual = {agent["id"]: agent["model"] for agent in seed_agents}
        assert actual == expected_seed_models

    def test_model_diversity(self, seed_agents):
        """Verify we're using multiple different models"""
        models = {agent['model'] for agent in seed_agents}
        assert len(models) >= 2, "Should use at least 2 different models for diversity"


class TestAgentTools:
    """Test agent tool assignments"""

    def test_common_tools_available(self, seed_agents):
        """Verify common tools are used across agents"""
        all_tools = set()
        for agent in seed_agents:
            all_tools.update(agent['tools'])

        # Common tools that should be available
        assert 'memory' in all_tools, "memory tool should be used"
        assert 'json' in all_tools, "json tool should be used"

    def test_web_search_tool_usage(self, seed_agents):
        """Verify web_search tool is used by research agents"""
        research_agents = [
            a for a in seed_agents
            if 'research' in a['agentType'].lower()
            or 'research' in a['domain'].lower()
            or 'intelligence' in a['domain'].lower()
        ]

        # At least some research agents should have web_search
        agents_with_search = [a for a in research_agents if 'web_search' in a['tools']]
        assert len(agents_with_search) > 0, "Research agents should have web_search tool"

    def test_calculator_tool_usage(self, seed_agents):
        """Verify calculator tool is used by analytical agents"""
        analytical_agents = [
            a for a in seed_agents
            if 'financial' in a['domain'].lower()
            or 'data-science' in a['subdomain'].lower()
        ]

        if analytical_agents:
            agents_with_calc = [a for a in analytical_agents if 'calculator' in a['tools']]
            assert len(agents_with_calc) > 0, "Analytical agents should have calculator tool"


class TestAgentStatus:
    """Test agent status and availability"""

    def test_all_agents_active(self, seed_agents):
        """Verify all agents are marked as active"""
        for agent in seed_agents:
            assert agent['status'] == 'active', \
                f"Agent {agent['id']} should be active, got: {agent['status']}"

    def test_agents_have_creation_dates(self, seed_agents):
        """Verify all agents have creation dates"""
        for agent in seed_agents:
            assert agent['createdAt'], \
                f"Agent {agent['id']} missing createdAt field"
            assert 'T' in agent['createdAt'], \
                f"Agent {agent['id']} createdAt not in ISO format"

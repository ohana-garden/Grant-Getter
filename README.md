# Grant Agent Extension for Agent Zero

AI-powered grant finder and writer built on the [Agent Zero](https://github.com/agent0ai/agent-zero) framework.

## Overview

This extension transforms Agent Zero into a specialized grant writing assistant for nonprofits, charities, and community organizations. It combines grant discovery, intelligent proposal writing, compliance checking, and deadline management into a unified AI agent.

### What It Does

- **Discovers Grants**: Searches Grants.gov and other sources for relevant opportunities
- **Writes Proposals**: Generates compelling, compliant grant applications section-by-section
- **Ensures Compliance**: Validates proposals against funder requirements
- **Tracks Deadlines**: Manages submission schedules and sends reminders
- **Learns Continuously**: Remembers your organization and improves over time

### Key Features

✅ Hierarchical agent system (delegates tasks to specialized sub-agents)  
✅ Persistent memory (stores org data, past proposals, successful patterns)  
✅ Real-time streaming interface (watch the agent think and intervene)  
✅ Prompt-based behavior (easy to customize without coding)  
✅ Docker isolated (safe execution environment)  
✅ Extensible (add your own grant sources and tools)  

## Architecture

Built on Agent Zero's proven patterns:
- **Prompt-based**: All behavior defined in markdown files in `/prompts/grant_agent/`
- **Tool System**: 4 specialized grant tools that integrate with Agent Zero
- **Memory Areas**: Organized knowledge retention (facts, solutions, fragments)
- **Monologue Loop**: Transparent agent reasoning with user intervention

### Components

```
grant-agent/
├── python/
│   ├── tools/                    # Grant-specific tools
│   │   ├── grant_discovery.py    # Search opportunities
│   │   ├── proposal_writer.py    # Generate proposals
│   │   ├── compliance_checker.py # Validate requirements
│   │   └── deadline_tracker.py   # Manage deadlines
│   └── helpers/                  # Support utilities
├── prompts/grant_agent/          # Behavior definitions
│   ├── agent.system.md           # Main agent persona
│   ├── tool.grant_discovery.md   # Discovery tool guide
│   └── tool.proposal_writer.md   # Writing tool guide
├── data/
│   ├── templates/                # Proposal templates
│   └── deadlines.json            # Tracked deadlines
├── docs/                         # Documentation
└── tests/                        # Test suite
```

## Installation

### Prerequisites

- Agent Zero installed and working ([installation guide](https://github.com/agent0ai/agent-zero/blob/main/docs/installation.md))
- Docker Desktop running
- Python 3.11+
- Git

### Quick Install

1. **Clone this extension**:
```bash
cd /path/to/agent-zero
git clone https://github.com/yourusername/grant-agent.git extensions/grant-agent
```

2. **Copy tools to Agent Zero**:
```bash
cp extensions/grant-agent/python/tools/* python/tools/
```

3. **Copy prompts**:
```bash
cp -r extensions/grant-agent/prompts/grant_agent prompts/
```

4. **Install dependencies**:
```bash
pip install python-docx --break-system-packages
```

5. **Set environment variables** in `.env`:
```bash
# Optional: Add API keys for live grant sources
GRANTS_GOV_API_KEY=your_key_here
```

6. **Start Agent Zero in Grant Mode**:
```bash
python run_ui.py
```

In settings, set "Prompts Subdirectory" to `grant_agent`.

### Manual Setup

See [INSTALL.md](docs/INSTALL.md) for detailed step-by-step instructions.

## Usage

### Basic Workflow

1. **Tell the agent about your organization**:
```
I'm from Youth Learning Center, a nonprofit providing after-school tutoring 
to underserved students. Our annual budget is $250,000 and we serve about 
150 students per year.
```

2. **Find grants**:
```
Find grants for youth education programs in my area. We need at least 
$50,000 and have 60-90 days to apply.
```

3. **Write a proposal**:
```
Let's write a proposal for the Department of Education grant ED-2025-001.
```

4. **Track deadlines**:
```
Add this grant to my deadline tracker with a reminder 2 weeks before the deadline.
```

### Example Conversation

```
User: Find grants for environmental education programs.

Agent: I'll search for relevant environmental education grants.

[Uses grant_discovery tool]

I found 3 excellent matches:

1. **EPA Environmental Education Grants** - Environmental Protection Agency
   - Amount: $25,000 - $250,000
   - Deadline: March 15, 2026 (45 days from now)
   - Why it fits: Specifically funds environmental education programs like yours. 
     Your organization's 501c3 status qualifies, and the funding range matches 
     your project scope.

2. **NOAA B-WET Program** - National Oceanic and Atmospheric Administration
   - Amount: $50,000 - $200,000  
   - Deadline: April 30, 2026 (75 days from now)
   - Why it fits: Targets K-12 environmental education. Strong match if your 
     program involves watershed or marine topics.

Would you like me to add these to your deadline tracker or start drafting 
a proposal for any of them?
```

## Tool Reference

### grant_discovery

Search for grants across multiple sources.

```python
grant_discovery(
    keywords="youth education tutoring",
    org_type="nonprofit",
    topic_areas=["education", "youth"],
    max_results=10,
    min_amount=50000,
    deadline_within_days=90
)
```

**Returns**: List of opportunities with relevance scores

### proposal_writer

Generate proposal sections.

```python
proposal_writer(
    grant_id="ED-2025-001",
    section="need",  # abstract|need|goals|methods|budget|evaluation|capacity
    org_profile={...},
    action="generate",  # or "refine"
    requirements={'max_words': 1000, ...}
)
```

**Returns**: Section content with compliance status

### compliance_checker

Validate against funder rules.

```python
compliance_checker(
    proposal_sections={'need': content, 'goals': content},
    grant_requirements={...}
)
```

**Returns**: Compliance report with issues and warnings

### deadline_tracker

Manage submission deadlines.

```python
deadline_tracker(
    action="add",  # add|list|upcoming|remove
    grant_id="ED-2025-001",
    deadline="2026-03-15T23:59:59",
    notification_days_before=14
)
```

**Returns**: Status and deadline information

## Customization

### Modify Agent Behavior

Edit `/prompts/grant_agent/agent.system.md` to change:
- Communication style
- Workflow steps
- Quality standards
- Delegation strategy

### Add Grant Sources

Extend `grant_discovery.py`:
```python
async def _search_foundation_directory(self, keywords):
    # Add your API integration here
    pass
```

### Customize Templates

Edit section templates in `proposal_writer.py` or add custom templates in `/data/templates/`.

### Adjust Tool Guidance

Modify tool-specific prompts in `/prompts/grant_agent/tool.*.md` to change how Agent Zero uses each tool.

## Production Setup

For production deployment:

1. **Add real API integrations**:
   - Replace mock data in `grant_discovery.py` with actual Grants.gov API calls
   - Add Foundation Directory Online integration
   - Configure state/local grant portal scrapers

2. **Set up database** (optional):
   - PostgreSQL for grant opportunities and proposals
   - See `python/helpers/grant_database.py` for schema

3. **Configure calendar integrations**:
   - Google Calendar API
   - Microsoft Outlook API

4. **Enable notifications**:
   - Email reminders for deadlines
   - SMS alerts (via Twilio or similar)

5. **Add authentication**:
   - Multi-user support with role-based access
   - Team collaboration features

## Testing

Run the test suite:

```bash
cd extensions/grant-agent
python -m pytest tests/
```

Test individual tools:

```bash
python -m pytest tests/test_grant_discovery.py -v
```

## Troubleshooting

### Tools not loading

Ensure tools are in Agent Zero's `/python/tools/` directory:
```bash
ls python/tools/ | grep grant
```

### Prompts not active

Check settings in Agent Zero UI:
- "Prompts Subdirectory" should be set to `grant_agent`
- Restart Agent Zero after changing

### Memory not persisting

Agent Zero stores memory in `/memory/` directory. Ensure Docker volume is mounted correctly.

### Import errors

Install missing dependencies:
```bash
pip install python-docx --break-system-packages
```

## Roadmap

- [ ] Live Grants.gov API integration
- [ ] Foundation Directory Online connector
- [ ] Budget calculator tool
- [ ] Proposal collaboration features
- [ ] Success rate analytics
- [ ] Fine-tuned grant writing model
- [ ] Mobile app for deadline notifications

## Contributing

Contributions welcome! Please:
1. Fork this repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

This extension is built on [Agent Zero](https://github.com/agent0ai/agent-zero), which is also MIT licensed.

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/grant-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/grant-agent/discussions)
- **Agent Zero Discord**: [Join Server](https://discord.gg/B8KZKNsPpj)

## Acknowledgments

Built on the excellent [Agent Zero framework](https://github.com/agent0ai/agent-zero) by Jan Tomášek.

Inspired by the needs of nonprofit organizations working to fund their missions.

---

**Empowering nonprofits to secure the resources they need to serve their communities.**

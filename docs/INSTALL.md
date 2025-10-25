# Installation Guide - Grant Agent Extension

Complete step-by-step instructions for installing the Grant Agent extension for Agent Zero.

## Prerequisites

Before installing, ensure you have:

- ✅ **Agent Zero** installed and running ([install guide](https://github.com/agent0ai/agent-zero/blob/main/docs/installation.md))
- ✅ **Docker Desktop** installed and running
- ✅ **Python 3.11+** installed
- ✅ **Git** installed
- ✅ Basic familiarity with command line/terminal

## Installation Methods

### Method 1: Quick Install (Recommended)

This method copies the grant agent files directly into your existing Agent Zero installation.

**Step 1: Navigate to your Agent Zero directory**
```bash
cd /path/to/agent-zero
```

**Step 2: Download grant agent extension**

Option A - If you have the extension as a Git repository:
```bash
git clone https://github.com/yourusername/grant-agent.git extensions/grant-agent
```

Option B - If you have the extension as a ZIP file:
```bash
# Extract ZIP to extensions/grant-agent/
mkdir -p extensions
unzip grant-agent.zip -d extensions/
```

**Step 3: Copy tools to Agent Zero**
```bash
# Copy grant tools
cp extensions/grant-agent/python/tools/* python/tools/

# Verify tools were copied
ls python/tools/ | grep grant
```

You should see:
- `grant_discovery.py`
- `proposal_writer.py`
- `compliance_checker.py`
- `deadline_tracker.py`

**Step 4: Copy prompts**
```bash
# Copy grant prompts
cp -r extensions/grant-agent/prompts/grant_agent prompts/

# Verify prompts were copied
ls prompts/grant_agent/
```

You should see:
- `agent.system.md`
- `tool.grant_discovery.md`
- `tool.proposal_writer.md`

**Step 5: Install Python dependencies**
```bash
pip install python-docx --break-system-packages
```

**Step 6: Configure environment (optional)**

Edit your `.env` file to add grant-specific settings:
```bash
nano .env
```

Add these lines:
```bash
# Grant API Keys (optional - use mock data without these)
GRANTS_GOV_API_KEY=your_key_here
FOUNDATION_DIRECTORY_API_KEY=your_key_here
```

**Step 7: Start Agent Zero**
```bash
# If using web UI
python run_ui.py

# If using CLI
python run_cli.py
```

**Step 8: Enable Grant Mode**

In the Agent Zero web interface:
1. Click the **Settings** button (gear icon)
2. Find **"Prompts Subdirectory"**
3. Change from `default` to `grant_agent`
4. Click **Save**
5. Restart Agent Zero (click Restart button)

**Step 9: Test the installation**

In the chat, type:
```
Find grants for youth education programs.
```

If you see the agent use the `grant_discovery` tool and return grant opportunities, the installation is successful!

---

### Method 2: Standalone Development Setup

This method keeps grant agent separate, useful for development or testing.

**Step 1: Clone grant agent**
```bash
git clone https://github.com/yourusername/grant-agent.git
cd grant-agent
```

**Step 2: Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**Step 3: Install dependencies**
```bash
pip install -r requirements.txt
```

**Step 4: Run tests**
```bash
pytest tests/ -v
```

**Step 5: Integration with Agent Zero**

To use with Agent Zero, follow steps 3-9 from Method 1 to copy files into your Agent Zero installation.

---

## Verification Checklist

After installation, verify everything works:

- [ ] Agent Zero starts without errors
- [ ] Settings show `grant_agent` as prompts subdirectory
- [ ] Test message triggers grant_discovery tool
- [ ] Agent can generate proposal sections
- [ ] Deadline tracker stores deadlines
- [ ] Compliance checker validates content

### Quick Verification Commands

Test each tool individually:

**1. Grant Discovery**
```
Find grants for environmental education with a minimum of $50,000.
```

**2. Proposal Writer**
```
Write an abstract section for a youth tutoring program. Our organization is Youth Learning Center, a nonprofit providing after-school tutoring to 150 students annually.
```

**3. Compliance Checker**
```
Check if my abstract meets the 250-word limit: [paste your abstract]
```

**4. Deadline Tracker**
```
Add a deadline for grant ED-2025-001 on March 15, 2026.
```

---

## Troubleshooting

### Issue: Tools not found

**Symptom**: Agent says "I don't have a grant_discovery tool"

**Solution**:
```bash
# Verify tools exist
ls python/tools/ | grep grant

# If missing, copy again
cp extensions/grant-agent/python/tools/* python/tools/
```

### Issue: Wrong prompts active

**Symptom**: Agent behaves like regular Agent Zero, not grant-focused

**Solution**:
1. Open Settings in Agent Zero UI
2. Set "Prompts Subdirectory" to `grant_agent`
3. Click Save
4. Restart Agent Zero

### Issue: Import errors

**Symptom**: `ModuleNotFoundError: No module named 'docx'`

**Solution**:
```bash
pip install python-docx --break-system-packages
```

### Issue: Deadline tracker file errors

**Symptom**: `FileNotFoundError: [Errno 2] No such file or directory: '.../deadlines.json'`

**Solution**:
```bash
mkdir -p /home/claude/grant-agent/data
```

Or edit `deadline_tracker.py` line 24 to change storage path to a valid directory.

### Issue: Tests fail

**Symptom**: Pytest shows failures

**Solution**:
```bash
# Install test dependencies
pip install pytest pytest-asyncio --break-system-packages

# Run tests with verbose output
pytest tests/ -v

# Run specific test
pytest tests/test_grant_tools.py::TestGrantDiscovery -v
```

---

## Advanced Configuration

### Custom Grant Sources

To add additional grant sources beyond Grants.gov:

1. Edit `python/tools/grant_discovery.py`
2. Add new method (e.g., `_search_your_source()`)
3. Call from `execute()` method
4. Merge results with existing opportunities

### Custom Proposal Templates

To customize proposal templates:

1. Create templates in `data/templates/`
2. Edit `proposal_writer.py` to load custom templates
3. Modify section prompts in `prompts/grant_agent/tool.proposal_writer.md`

### Database Integration (Optional)

For production deployment with PostgreSQL:

1. Install PostgreSQL client:
```bash
pip install psycopg2-binary sqlalchemy --break-system-packages
```

2. Create database:
```sql
CREATE DATABASE grant_agent;
```

3. Set DATABASE_URL in `.env`:
```bash
DATABASE_URL=postgresql://user:pass@localhost/grant_agent
```

4. Run migrations:
```bash
python python/helpers/grant_database.py
```

### Calendar Integration (Optional)

To sync deadlines with Google Calendar:

1. Get Google Calendar API credentials
2. Install Google client:
```bash
pip install google-api-python-client --break-system-packages
```

3. Add to `.env`:
```bash
GOOGLE_CALENDAR_API_KEY=your_key
```

4. Modify `deadline_tracker.py` to call Calendar API

---

## Updating

To update grant agent to a new version:

**Step 1: Backup current installation**
```bash
cp -r extensions/grant-agent extensions/grant-agent-backup
```

**Step 2: Pull latest changes**
```bash
cd extensions/grant-agent
git pull origin main
```

**Step 3: Re-copy files**
```bash
cp python/tools/* ../../python/tools/
cp -r prompts/grant_agent ../../prompts/
```

**Step 4: Update dependencies**
```bash
pip install -r requirements.txt --upgrade --break-system-packages
```

**Step 5: Restart Agent Zero**

---

## Uninstalling

To remove grant agent:

**Step 1: Remove tools**
```bash
cd /path/to/agent-zero
rm python/tools/grant_discovery.py
rm python/tools/proposal_writer.py
rm python/tools/compliance_checker.py
rm python/tools/deadline_tracker.py
```

**Step 2: Remove prompts**
```bash
rm -r prompts/grant_agent
```

**Step 3: Reset Agent Zero settings**
1. Open Settings
2. Set "Prompts Subdirectory" back to `default`
3. Save and restart

---

## Getting Help

If you encounter issues not covered here:

1. **Check logs**: Agent Zero logs are in `logs/` directory
2. **GitHub Issues**: [Open an issue](https://github.com/yourusername/grant-agent/issues)
3. **Agent Zero Discord**: [Join for support](https://discord.gg/B8KZKNsPpj)
4. **Documentation**: Read the full [README.md](../README.md)

---

## Next Steps

After installation:

1. **Configure your organization profile** - Tell the agent about your nonprofit
2. **Search for grants** - Find relevant opportunities
3. **Write your first proposal** - Let the agent guide you through the process
4. **Set up deadline tracking** - Never miss a submission deadline

See [README.md](../README.md) for usage examples and best practices.

---

**You're ready to start finding and winning grants!**

# Quick Start Guide - Grant Agent

Get started with the Grant Agent extension in 5 minutes.

## 1. Install (2 minutes)

```bash
# Navigate to Agent Zero
cd /path/to/agent-zero

# Copy grant tools
cp extensions/grant-agent/python/tools/* python/tools/

# Copy prompts
cp -r extensions/grant-agent/prompts/grant_agent prompts/

# Install dependency
pip install python-docx --break-system-packages
```

## 2. Configure (1 minute)

Start Agent Zero:
```bash
python run_ui.py
```

In the web UI:
1. Click **Settings** (gear icon)
2. Set "Prompts Subdirectory" to `grant_agent`
3. Click **Save**
4. Click **Restart**

## 3. First Conversation (2 minutes)

Try this:

```
User: I'm from Hope Community Center, a nonprofit serving homeless families. 
We need to find grants for housing assistance programs.

Agent: [Greets you and stores org info]

User: Find grants for housing assistance with at least $100,000.

Agent: [Uses grant_discovery tool and shows results]

User: Write a proposal for the first grant you found.

Agent: [Guides you through proposal writing step-by-step]
```

## Common Commands

**Search for grants:**
```
Find grants for [your cause] with minimum $[amount]
```

**Write proposals:**
```
Write a [section] for grant [ID]. Our organization is [description].
```

**Track deadlines:**
```
Add grant [ID] to my deadline tracker with deadline [date]
```

**Check compliance:**
```
Check if my proposal meets the requirements for [grant]
```

## Tips for Best Results

1. **Tell the agent about your organization first** - it stores this in memory
2. **Be specific with keywords** - "youth literacy tutoring" not just "education"  
3. **Review each section** - the agent presents drafts for your approval
4. **Let it guide you** - it knows the grant writing process

## Need Help?

- **Documentation**: See [README.md](../README.md)
- **Installation Issues**: See [INSTALL.md](docs/INSTALL.md)
- **Questions**: Open a GitHub issue

---

**That's it! You're ready to find and win grants with AI assistance.**

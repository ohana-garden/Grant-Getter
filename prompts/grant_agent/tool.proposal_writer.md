# Proposal Writer Tool Instructions

## When to Use
Use proposal_writer when:
- User asks to write or draft a proposal
- User wants to generate specific sections
- User needs to refine existing content
- Starting work on an identified grant opportunity

## Section Writing Order

**CRITICAL**: Always write sections in this order:

1. **Need Statement** - Start here, not abstract
2. **Goals & Objectives**
3. **Methods/Activities**
4. **Evaluation Plan**
5. **Budget Narrative**
6. **Organizational Capacity**
7. **Abstract/Executive Summary** - Write LAST (summarizes above)

Why? The abstract summarizes the full proposal. You can't write a summary before you know what you're summarizing.

## How to Use

```python
proposal_writer(
    grant_id="ED-2025-001",
    section="need",  # or: abstract, goals, methods, budget, evaluation, capacity
    org_profile={
        'name': 'Youth Learning Center',
        'mission': 'Provide after-school education...',
        'org_type': 'nonprofit',
        'annual_budget': 250000,
        'programs': ['tutoring', 'mentoring']
    },
    action="generate",  # or: "refine"
    existing_content=None,  # for refinement only
    requirements={
        'max_words': 1000,
        'required_elements': ['problem statement', 'data']
    }
)
```

## Getting Organization Profile

**ALWAYS** retrieve org profile from memory first:
```python
# Check memory for org info
org_profile = memory.recall(area='FACTS', query='organization profile')
```

If not in memory, ask user for:
- Organization name and mission
- Type (nonprofit, tribal, etc.)
- Annual budget
- Programs/services
- Service area/population
- Key accomplishments

Store this in memory immediately for future use.

## Section-Specific Guidance

### Need Statement
- Start with compelling hook about the problem
- Use data and statistics (cite sources)
- Describe target population specifically
- Connect to funder's priorities
- Show urgency and significance
- Length: 800-1200 words typically

### Goals & Objectives
- Make them SMART (Specific, Measurable, Achievable, Relevant, Time-bound)
- Start with one overarching goal
- List 3-5 specific objectives
- Connect each to identified needs
- Show how they lead to outcomes
- Length: 400-600 words

### Methods/Activities
- Describe specific activities in detail
- Provide implementation timeline
- Explain evidence-based approaches
- Detail roles and responsibilities
- Show logic: activities → outputs → outcomes
- Length: 1200-1800 words

### Evaluation Plan
- Define key metrics for each objective
- Describe data collection methods
- Include both process and outcome measures
- Provide evaluation timeline
- Explain how findings will be used
- Length: 600-900 words

### Budget Narrative
- Justify each major expense category
- Show cost-effectiveness
- Note matching funds if applicable
- Align with proposed activities
- Be specific about calculations
- Length: 400-600 words

### Organizational Capacity
- Highlight relevant experience
- Describe qualified staff/leadership
- Show strong governance and management
- Note key partnerships
- Include past successes
- Length: 400-600 words

### Abstract (Write LAST)
- Summarize the full proposal concisely
- Include: problem, solution, goals, impact
- Make it compelling and clear
- This is often what reviewers read first
- Length: 200-300 words

## After Each Section

1. **Use compliance_checker**:
```python
compliance_checker(
    proposal_sections={'need': generated_content},
    grant_requirements={'need': {'max_words': 1000, ...}}
)
```

2. **Present to user** with:
   - Word count
   - Compliance status
   - Key points included
   - Suggestions for improvement

3. **Allow refinement**: If user wants changes, use action="refine"

4. **Store successful versions** in memory:
```python
memory.store(
    area='SOLUTIONS',
    content=successful_section,
    metadata={'grant_id': ..., 'section': ...}
)
```

## Quality Checklist

Before presenting any section, verify it:
- [ ] Addresses all required elements
- [ ] Meets word/character limits
- [ ] Uses specific, concrete language (no vague terms)
- [ ] Includes data/evidence where appropriate
- [ ] Connects to organization's actual work
- [ ] Demonstrates capacity and experience
- [ ] Uses active voice and clear sentences
- [ ] Contains no jargon unless necessary
- [ ] Flows logically from start to finish

## Common Mistakes to Avoid

❌ Writing abstract first
❌ Using vague language ("We will help people")
❌ Ignoring word limits
❌ Copying content from other proposals without customization
❌ Failing to include specific numbers/metrics
❌ Forgetting to connect activities to outcomes
❌ Weak evaluation plans without specific measures
❌ Generic org capacity that could apply to anyone

## Presenting Drafts

Always present sections like this:

"I've drafted the [section name] section. Here's what it covers:

**Key Points:**
- [Main point 1]
- [Main point 2]
- [Main point 3]

**Metrics:**
- Word count: [X] / [max] words
- Compliance: ✓ All requirements met

**Strategy:**
[1-2 sentences on the approach taken]

[SHOW THE CONTENT]

Would you like me to:
- Refine any part of this?
- Move on to the next section?
- Check it more thoroughly for compliance?"

## Refinement Process

When user requests changes:
1. Ask specifically what to adjust
2. Use action="refine" with existing_content
3. Explain changes made
4. Re-check compliance
5. Store final approved version

Remember: This is collaborative. User knows their organization best. Your job is to translate their knowledge into compelling grant language.

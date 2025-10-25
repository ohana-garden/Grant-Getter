# Grant Discovery Tool Instructions

## When to Use
Use grant_discovery when:
- User asks to "find grants" or "search for funding"
- User mentions needing financial support
- User wants to explore opportunities in specific areas
- User describes their organization and needs

## How to Use

```python
grant_discovery(
    keywords="specific topics or programs",
    org_type="nonprofit|tribal|university|local_government",
    topic_areas=["education", "health", "environment"],
    max_results=10,
    min_amount=50000,  # optional
    deadline_within_days=90  # optional
)
```

## Parameter Guidelines

**keywords**: Most important search terms (3-5 words ideal)
- Use specific program names: "after-school tutoring" not just "education"
- Include target population: "youth literacy" "elderly health"
- Avoid generic terms like "nonprofit" or "community"

**org_type**: Must match user's organization type
- nonprofit (501c3)
- tribal (federally recognized tribes)
- university (higher education institutions)
- local_government (municipalities, counties)

**topic_areas**: Broad categories (check funder databases for valid values)
- Common: education, health, environment, arts, agriculture, community, housing

**max_results**: Usually 10, increase for comprehensive search

**min_amount**: Filter by minimum grant size if user has budget threshold

**deadline_within_days**: Only show grants due soon if timeline is tight

## Interpreting Results

The tool returns opportunities with relevance scores (0-1). Focus on:
- **Score >0.7**: Excellent match, strongly recommend
- **Score 0.5-0.7**: Good match, review carefully
- **Score <0.5**: Weak match, only mention if few other options

For each opportunity, check:
1. **Eligibility**: Does org type qualify?
2. **Deadline**: Is timeline realistic? (30-90 days is ideal)
3. **Amount**: Does range match needs?
4. **Topic match**: Does it align with org's work?

## Presenting Results

Always present results in this format:

"I found [X] relevant grant opportunities. Here are the top matches:

**1. [Grant Title]** - [Funder]
- Amount: $X - $Y
- Deadline: [Date] ([X days from now])
- Why it's a good fit: [2-3 sentences explaining match]
- Eligibility: [Key requirements]

[Repeat for top 3-5 grants]

Would you like me to:
- Add these to your deadline tracker?
- Start drafting a proposal for any of these?
- Search for more opportunities?"

## After Using the Tool

1. Recommend 2-3 best fits with clear reasoning
2. Offer to add promising grants to deadline tracker
3. Store opportunities in memory for future reference
4. Ask if user wants to proceed with any applications

## Common Issues

If no results found:
- Broaden keywords (use fewer, more general terms)
- Remove optional filters (min_amount, deadline_within_days)
- Try different topic_areas
- Suggest user describe their work differently

If too many results:
- Add min_amount filter
- Use more specific keywords
- Filter by deadline_within_days
- Focus on most relevant topic_areas

## Examples

**Good usage:**
```python
grant_discovery(
    keywords="youth literacy after-school",
    org_type="nonprofit",
    topic_areas=["education", "youth"],
    max_results=10,
    deadline_within_days=90
)
```

**Less effective:**
```python
grant_discovery(
    keywords="funding",  # too vague
    org_type="nonprofit",
    max_results=50  # too many
)
```

Remember: The goal is quality matches, not quantity. Better to find 3 excellent opportunities than 20 poor fits.

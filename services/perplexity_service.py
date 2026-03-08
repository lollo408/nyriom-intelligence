"""
Perplexity API integration for generating event summaries.
Two-pass approach:
  Pass 1 (sonar): Web research - gather raw facts and sources
  Pass 2 (sonar-pro): Business intelligence analysis
"""

import json
import os
import re
import requests
import nh3

PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY', '').strip()


ALLOWED_HTML_TAGS = {
    'h3', 'h4', 'p', 'ul', 'ol', 'li', 'a', 'strong', 'em',
    'hr', 'br', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
}
ALLOWED_HTML_ATTRIBUTES = {
    'a': {'href'},
}


def sanitize_html(html: str) -> str:
    """Sanitize HTML with an allowlist of safe tags and attributes."""
    if not html:
        return html
    cleaned = nh3.clean(
        html,
        tags=ALLOWED_HTML_TAGS,
        attributes=ALLOWED_HTML_ATTRIBUTES,
        link_rel='nofollow noopener',
    )
    return cleaned


def _clean_html_response(content: str) -> str:
    """Clean up AI-generated HTML response and sanitize."""
    if not content:
        return content
    content = re.sub(r'^```(?:html|HTML)?\s*\n?', '', content.strip())
    content = re.sub(r'\n?```\s*$', '', content.strip())
    # Strip inline citation numbers [1], [2], etc.
    content = re.sub(r'\s*\[\d+\]', '', content)
    # Convert stray markdown bold to HTML
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
    content = content.strip()
    # Sanitize to prevent XSS from AI-generated content
    return sanitize_html(content)


PERPLEXITY_API_URL = 'https://api.perplexity.ai/chat/completions'

NYRIOM_CONTEXT = """NYRIOM TECHNOLOGIES GmbH (Berlin, Germany):
- Advanced materials startup specializing in high-performance bio-based polymer composites
- Uses AI-driven molecular simulation and computational material science
- Partners with contract manufacturers (CMOs) across Europe for scale production
- Core product: Drop-in replacements for petroleum-derived engineering plastics (PA, PBT, PEEK alternatives)
- Plant-based feedstocks targeting applications where weight, thermal resistance, and sustainability matter

TARGET VERTICALS:
- Aerospace: Lightweight interior panels, structural brackets, secondary structures. Pursuing Airbus & Tier 1 qualifications.
- Automotive: EV battery enclosures, under-hood components, interior trim. Working with German OEMs on pilots.
- Robotics: Actuator housings, sensor enclosures, lightweight structural frames for warehouse and surgical robotics.
- AI/Electronics: Thermal management substrates, EMI shielding compounds, flexible circuit board substrates.

OPPORTUNITY INDICATORS (for scoring):
- New material qualification programs or RFPs announced
- Sustainability mandates or REACH/TSCA regulatory changes
- OEM lightweighting initiatives or EV platform announcements
- Robotics companies scaling production (moving from prototype to volume)
- Electronics thermal management challenges discussed
- Decision-makers present (procurement, engineering leads, CTOs)
- Contract manufacturing or supply chain reshoring announcements
- Bio-based or circular economy material mentions"""


def _call_perplexity(model: str, messages: list, timeout: int = 90) -> dict:
    """Helper to call Perplexity API."""
    if not PERPLEXITY_API_KEY:
        return {'success': False, 'content': None, 'error': 'PERPLEXITY_API_KEY not configured'}

    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': model,
        'messages': messages
    }

    try:
        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        content = data['choices'][0]['message']['content']
        return {'success': True, 'content': content, 'error': None}
    except requests.exceptions.Timeout:
        return {'success': False, 'content': None, 'error': 'API timeout'}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'content': None, 'error': str(e)}
    except (KeyError, IndexError) as e:
        return {'success': False, 'content': None, 'error': f'Invalid response: {e}'}


def _pass_one_research(event_name: str, event_date: str,
                        industry: str, location: str,
                        website: str = None) -> dict:
    """Pass 1: Web research using sonar-pro."""

    prompt = f"""Research this industry event thoroughly and provide a comprehensive factual report.

EVENT DETAILS:
- Name: {event_name}
- Date: {event_date}
- Industry: {industry}
- Location: {location}
{f'- Website: {website}' if website else ''}

GATHER THE FOLLOWING INFORMATION:

1. EVENT OVERVIEW
- What was the event about? (theme, focus, scale)
- How many attendees/exhibitors?
- Any notable sponsors or organizers?

2. KEY ANNOUNCEMENTS
- Product launches or unveilings
- Company announcements (expansions, partnerships, investments)
- New material innovations or manufacturing breakthroughs
- Awards or recognitions given

3. SPEAKERS & ATTENDEES
- Notable speakers and their topics
- Executives or decision-makers who attended
- Companies that exhibited or sponsored

4. INDUSTRY THEMES
- Major topics or trends discussed
- Sustainability, bio-materials, or circular economy discussions
- Advanced manufacturing or automation highlights
- Regulatory or policy mentions (REACH, TSCA, aerospace certifications)

5. MATERIALS & MANUFACTURING SPECIFIC (if applicable)
- New polymer or composite material announcements
- Lightweighting initiatives or programs
- EV-related material developments
- Supply chain or reshoring discussions
- Qualification or certification programs

6. SOURCES
- List all URLs where you found this information

FORMAT: Provide a detailed, factual report. Include specific names, companies, dates, and numbers where available. Do not analyze or editorialize - just report the facts."""

    return _call_perplexity('sonar', [{'role': 'user', 'content': prompt}])


def _pass_two_analysis(research: str, event_name: str,
                        industry: str) -> dict:
    """Pass 2: Business intelligence analysis using sonar-pro."""

    system_message = f"""You are a senior business intelligence analyst for Nyriom Technologies, preparing executive briefings on industry events.

{NYRIOM_CONTEXT}

Your task is to analyze event research and produce actionable business intelligence for Nyriom's commercial team. Be direct and honest - if there are no opportunities, say so, but always find value (trends, contacts, future potential).

ABSOLUTE RULES:
- NEVER output citation markers like [1], [2], [3] or any bracketed numbers. This is non-negotiable.
- Write concise executive briefings, not academic papers. Every sentence must earn its place."""

    prompt = f"""Based on this research about "{event_name}" ({industry} industry), create a business intelligence briefing.

RESEARCH DATA:
{research}

---

FORMAT YOUR RESPONSE AS HTML WITH THIS EXACT STRUCTURE:

<h3>Quick Assessment</h3>
<ul>
<li><strong>Opportunity Score:</strong> [HIGH / MEDIUM / LOW] — <em>[One line why]</em></li>
<li><strong>Nyriom Relevance:</strong> [HIGH / MEDIUM / LOW] — <em>[One line why]</em></li>
<li><strong>Urgency:</strong> [IMMEDIATE / NEAR-TERM / MONITOR] — <em>[One line why]</em></li>
</ul>

<h3>Immediate Actions</h3>
<ul>
<li><strong>Action:</strong> Specific thing to do now, with contact or company name [1-2 sentences]</li>
</ul>

<h3>Opportunities Identified</h3>
<ul>
<li><strong>[Company Name]:</strong> What they announced — why it matters to Nyriom [2-3 sentences max]</li>
[3-5 items. Quality over quantity.]
</ul>

<h3>Market Intelligence</h3>
<ul>
<li><strong>[Trend]:</strong> What to watch and why [1 sentence]</li>
[3 items max]
</ul>

<h3>Key Contacts</h3>
<ul>
<li><strong>Name, Title @ Company</strong> — Why they matter [1 sentence]</li>
</ul>

<h3>Sources</h3>
<ul>
<li><a href="https://actual-url.com/path">Source title or description</a></li>
[All sources as clickable links — this is the ONLY place URLs should appear]
</ul>

<hr>
<h3>Event Recap</h3>
<p>[1-2 concise paragraphs summarizing what happened. No business lens, just the event itself.]</p>

RULES:
1. NEVER use inline citations [1], [2], [3] or bracketed numbers — ZERO TOLERANCE
2. Output ONLY valid HTML, no markdown or code blocks
3. All sources as clickable <a href> links in the Sources section
4. Be specific: company names, dollar amounts, timelines
5. Aim for 800-1000 words total. If a bullet exceeds 3 sentences, it's too long.
6. No filler phrases ("It is worth noting", "Importantly", "Additionally", "Furthermore")
7. Be honest about limitations - if data is thin, say so"""

    return _call_perplexity(
        'sonar-pro',
        [
            {'role': 'system', 'content': system_message},
            {'role': 'user', 'content': prompt}
        ],
        timeout=120
    )


def generate_event_summary(event_name: str, event_date: str,
                           industry: str, location: str,
                           website: str = None) -> dict:
    """
    Generate a comprehensive event summary using two-pass approach.

    Pass 1 (sonar): Web research - gather raw facts
    Pass 2 (sonar-pro): Business intelligence analysis
    """
    research_result = _pass_one_research(event_name, event_date, industry, location, website)

    if not research_result['success']:
        return {
            'success': False,
            'summary': None,
            'error': f"Pass 1 (Research) failed: {research_result['error']}"
        }

    research_data = research_result['content']
    analysis_result = _pass_two_analysis(research_data, event_name, industry)

    if not analysis_result['success']:
        return {
            'success': False,
            'summary': None,
            'error': f"Pass 2 (Analysis) failed: {analysis_result['error']}"
        }

    cleaned_summary = _clean_html_response(analysis_result['content'])

    return {
        'success': True,
        'summary': cleaned_summary,
        'error': None
    }


# ---------------------------------------------------------------------------
# Intelligence Report Generation (two-pass pipeline)
# ---------------------------------------------------------------------------

VERTICAL_DISPLAY_NAMES = {
    'aerospace': 'Aerospace & Defense',
    'automotive': 'Automotive & EV',
    'robotics': 'Robotics & Automation',
    'ai_electronics': 'AI, Semiconductors & Electronics',
}

VERTICAL_FOCUS = {
    'aerospace': 'aircraft structures, satellite systems, defense platforms, space launch vehicles, MRO, Airbus/Boeing supply chains, Tier 1 aerostructures suppliers',
    'automotive': 'electric vehicles, battery systems, OEM platforms, lightweighting programs, under-hood components, interior trim, German OEMs (VW, BMW, Mercedes), Tier 1 automotive suppliers',
    'robotics': 'warehouse automation, surgical robotics, collaborative robots, actuator and sensor systems, industrial automation, humanoid robots, drone systems',
    'ai_electronics': 'semiconductors, AI accelerators, thermal management, EMI shielding, flexible electronics, PCB substrates, edge computing hardware, consumer electronics miniaturization',
}


def _intelligence_pass_one_research(vertical: str, as_of_date: str = None) -> dict:
    """Pass 1: Research latest industry news/trends for the vertical using sonar-pro."""
    display_name = VERTICAL_DISPLAY_NAMES.get(vertical, vertical)
    focus = VERTICAL_FOCUS.get(vertical, '')

    time_frame = f"as of {as_of_date}" if as_of_date else "from the last 2-4 weeks"

    prompt = f"""Research the latest industry news and developments {time_frame} in the {display_name} sector.

FOCUS AREAS for this vertical: {focus}

GATHER THE FOLLOWING INFORMATION:

1. LATEST NEWS & ANNOUNCEMENTS
- Major product launches, new platform announcements
- Partnerships, joint ventures, M&A activity
- Funding rounds, IPOs, major investments
- Company expansions, new facilities, production milestones

2. REGULATORY & POLICY UPDATES
- New regulations, standards, or certifications
- Government programs, subsidies, or mandates
- Trade policy changes affecting supply chains
- Environmental or sustainability regulations

3. MATERIALS & MANUFACTURING
- New material innovations (polymers, composites, advanced materials)
- Lightweighting initiatives or programs
- Bio-based or sustainable material developments
- Supply chain shifts, reshoring, new supplier qualifications
- Contract manufacturing announcements

4. MARKET TRENDS
- Industry growth or contraction signals
- Technology adoption trends
- Competitive landscape shifts
- Demand signals from end customers

5. SPECIFIC TO ADVANCED MATERIALS / COMPOSITES / POLYMERS
- Any announcements related to engineering plastics, high-performance polymers, or composite materials
- Thermal management material developments
- Weight reduction programs that could use polymer composites
- Sustainability-driven material substitution

6. SOURCES
- List all URLs where you found this information

FORMAT: Provide a detailed, factual report with specific company names, dates, numbers, and URLs. Do not analyze or editorialize - just report the facts.

CRITICAL FORMAT RULES:
- Do NOT use inline citation numbers like [1], [2], [3] anywhere
- Do NOT use footnote-style references
- List source URLs in the SOURCES section only
- Write in plain prose, not academic citation style"""

    return _call_perplexity('sonar', [{'role': 'user', 'content': prompt}])


def _intelligence_pass_two_analysis(research: str, vertical: str, as_of_date: str = None) -> dict:
    """Pass 2: Generate business intelligence analysis using sonar-pro."""
    display_name = VERTICAL_DISPLAY_NAMES.get(vertical, vertical)
    time_context = f" as of {as_of_date}" if as_of_date else ""

    system_message = f"""You are a senior business intelligence analyst for Nyriom Technologies, preparing periodic industry intelligence briefings for the executive team.

{NYRIOM_CONTEXT}

Your task is to analyze industry research{time_context} and produce an actionable intelligence report for Nyriom's leadership. Be specific and practical - focus on what matters for a bio-polymer composites startup trying to win business in the {display_name} vertical.

ABSOLUTE RULES:
- NEVER output citation markers like [1], [2], [3] or any bracketed numbers. This is non-negotiable.
- Write concise executive briefings, not academic papers. Every sentence must earn its place."""

    prompt = f"""Based on this research about the {display_name} sector{time_context}, create a business intelligence briefing.

RESEARCH DATA:
{research}

---

FORMAT YOUR RESPONSE IN TWO PARTS:

PART 1 — HTML REPORT (output first):

<h3>Executive Summary</h3>
<p>[1 concise paragraph, max 4 sentences. What happened and what it means for Nyriom.]</p>

<h3>Key Developments</h3>
<ul>
<li><strong>[Company/Entity]:</strong> What happened — why it matters for Nyriom [1-2 sentences per item]</li>
[4-6 items. Quality over quantity.]
</ul>

<h3>Opportunities for Nyriom</h3>
<ul>
<li><strong>[Opportunity]:</strong> Who to contact, what to propose, timeline [2-3 sentences max]</li>
[3-4 items. Only genuine, actionable leads.]
</ul>

<h3>Market Outlook</h3>
<ul>
<li><strong>[Trend]:</strong> What to watch and why [1 sentence]</li>
[3 items max]
</ul>

<h3>Sources</h3>
<ul>
<li><a href="https://actual-url.com/path">Source title or description</a></li>
[All sources as clickable links — this is the ONLY place URLs should appear]
</ul>

PART 2 — TOP 5 HEADLINES (output after the HTML, delimited by markers):

After the HTML report, output this EXACTLY:

<!-- TOP_5_JSON -->
[
    {{"headline": "Most important headline", "summary": "One sentence summary of why this matters", "source_url": "https://real-url.com/article"}},
    {{"headline": "Second headline", "summary": "One sentence summary", "source_url": "https://real-url.com/article2"}},
    {{"headline": "Third headline", "summary": "One sentence summary", "source_url": "https://real-url.com/article3"}},
    {{"headline": "Fourth headline", "summary": "One sentence summary", "source_url": "https://real-url.com/article4"}},
    {{"headline": "Fifth headline", "summary": "One sentence summary", "source_url": "https://real-url.com/article5"}}
]
<!-- /TOP_5_JSON -->

RULES:
1. NEVER use inline citations [1], [2], [3] or bracketed numbers — ZERO TOLERANCE
2. Output ONLY valid HTML, no markdown or code blocks
3. All sources as clickable <a href> links in the Sources section
4. Be specific: company names, dollar amounts, timelines
5. Aim for 800-1200 words total. If a bullet exceeds 3 sentences, it's too long.
6. No filler phrases ("It is worth noting", "Importantly", "Additionally")
7. Top 5 headlines: most impactful for Nyriom, with real source URLs
8. The JSON must be valid — use real source URLs from the research"""

    return _call_perplexity(
        'sonar-pro',
        [
            {'role': 'system', 'content': system_message},
            {'role': 'user', 'content': prompt}
        ],
        timeout=120
    )


def generate_intelligence_report(vertical: str, as_of_date: str = None) -> dict:
    """
    Generate an intelligence report for a vertical using two-pass approach.

    Pass 1 (sonar): Web research - gather raw industry news
    Pass 2 (sonar-pro): Business intelligence analysis + top 3 headlines

    Args:
        vertical: One of 'aerospace', 'automotive', 'robotics', 'ai_electronics'
        as_of_date: Optional date string (e.g. 'mid-February 2026') to scope research

    Returns:
        {'success': bool, 'report_html': str, 'top_3_json': list, 'error': str}
    """
    # Pass 1: Research
    research_result = _intelligence_pass_one_research(vertical, as_of_date)

    if not research_result['success']:
        return {
            'success': False,
            'report_html': None,
            'top_3_json': None,
            'error': f"Pass 1 (Research) failed: {research_result['error']}"
        }

    research_data = research_result['content']

    # Pass 2: Analysis
    analysis_result = _intelligence_pass_two_analysis(research_data, vertical, as_of_date)

    if not analysis_result['success']:
        return {
            'success': False,
            'report_html': None,
            'top_3_json': None,
            'error': f"Pass 2 (Analysis) failed: {analysis_result['error']}"
        }

    raw_content = analysis_result['content']

    # Parse: split HTML report from top-5 JSON (also handles legacy top-3)
    top_json = []
    report_html = raw_content

    # Try top-5 delimiters first, fall back to top-3
    if '<!-- TOP_5_JSON -->' in raw_content and '<!-- /TOP_5_JSON -->' in raw_content:
        parts = raw_content.split('<!-- TOP_5_JSON -->')
        report_html = parts[0].strip()
        json_block = parts[1].split('<!-- /TOP_5_JSON -->')[0].strip()
    elif '<!-- TOP_3_JSON -->' in raw_content and '<!-- /TOP_3_JSON -->' in raw_content:
        parts = raw_content.split('<!-- TOP_3_JSON -->')
        report_html = parts[0].strip()
        json_block = parts[1].split('<!-- /TOP_3_JSON -->')[0].strip()
    else:
        json_block = None

    if json_block:
        try:
            top_json = json.loads(json_block)
        except json.JSONDecodeError as e:
            # Try to salvage — sometimes the model wraps in code fences
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', json_block.strip())
            cleaned = re.sub(r'\n?```\s*$', '', cleaned.strip())
            try:
                top_json = json.loads(cleaned)
            except json.JSONDecodeError:
                top_json = [{'headline': 'Parse error', 'summary': str(e), 'source_url': ''}]

    report_html = _clean_html_response(report_html)

    return {
        'success': True,
        'report_html': report_html,
        'top_3_json': top_json,
        'error': None
    }

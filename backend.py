from typing import TypedDict
from duckduckgo_search import DDGS
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
import os
import re
from datetime import datetime

qwen = ChatOllama(
    model="qwen3:8b",
    temperature=0
)

deepseek = ChatOllama(
    model="deepseek-r1:8b",
    temperature=0
)

mistral = ChatOllama(
    model="mistral:latest",
    temperature=0
)

def extract_search_keywords(query):
    """
    Uses Qwen to extract only the important search keywords.
    This avoids searches like 'Future of Quantum Computing'
    becoming searches for the rapper 'Future'.
    """

    response = qwen.invoke(f"""
Extract only the important search keywords.

Query:
{query}

Rules:
- Remove filler words.
- Remove words like:
  future
  impact
  role
  application
  applications
  use
  using
  study
  analysis

- Preserve:
    • company names
    • technology names
    • scientific terms
    • product names
    • abbreviations

Examples

Future of Quantum Computing in NVIDIA

Quantum Computing, NVIDIA

Cybersecurity using AI

Cybersecurity, AI

Role of Blockchain in Supply Chain

Blockchain, Supply Chain

Return ONLY comma-separated keywords.
""")

    return clean_llm_output(response.content)

def clean_llm_output(text):
    """
    Qwen3 is a 'thinking' model — by default it can emit a <think>...</think>
    reasoning block ahead of its actual answer. If that block ends up inside
    response.content, it gets fed as if it were factual "research"/"analysis"
    into the next agent's prompt, and the model's raw, unconstrained chain-of-
    thought (which can drift completely off-topic) compounds into seemingly
    random hallucinated content a few agents downstream. Stripping it here
    keeps every agent's input to ONLY the intended final answer.
    """
    if not text:
        return text
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# Words too generic to use when judging whether a search result is
# actually about the requested topic.
_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "is", "are",
    "with", "what", "how", "why", "about", "using", "use", "vs", "or"
}


def _is_relevant(query, result):

    keywords = extract_search_keywords(query)

    keyword_list = [

        k.strip().lower()

        for k in keywords.split(",")

        if k.strip()

    ]

    text = (

        result.get("title", "") +

        " " +

        result.get("body", "")

    ).lower()

    matches = 0

    for keyword in keyword_list:

        if keyword in text:

            matches += 1

    required = max(

        1,

        len(keyword_list) // 2

    )

    return matches >= required


class AgentState(TypedDict):
    query: str
    search_results: str
    citations: str
    research: str
    analysis: str
    review: str
    metrics: str
    report: str


def web_search(query, max_results=5):
    """
    Returns structured search results: [{ "title", "href", "body" }, ...]
    Using duckduckgo-search's DDGS instead of DuckDuckGoSearchRun, which
    only returns a single unstructured paragraph (no titles/URLs at all).
    """
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return results


# Domains that are almost always noise for a research report, regardless
# of topic.
_BAD_DOMAINS = [
    "youtube.com",
    "instagram.com",
    "facebook.com",
    "tiktok.com",
    "spotify.com",
]

# Domains worth ranking higher when present — gov/edu/standards bodies,
# academic preprint servers, and major tech vendors.
_GOOD_DOMAINS = [
    ".gov",
    ".edu",
    "nvidia.com",
    "ibm.com",
    "microsoft.com",
    "nature.com",
    "ieee.org",
    "arxiv.org",
]


def _is_bad_domain(result):
    url = result.get("href", "").lower()
    return any(domain in url for domain in _BAD_DOMAINS)


def _domain_score(result):
    url = result.get("href", "").lower()
    return sum(5 for d in _GOOD_DOMAINS if d in url)


def _build_search_queries(query):

    keywords = extract_search_keywords(query)

    keyword_string = keywords.replace(",", " ")

    return [

        keyword_string,

        f"{keyword_string} research",

        f"{keyword_string} technology",

        f"{keyword_string} industry",

        f"{keyword_string} latest",

        f"{keyword_string} review",

    ]


def web_search_multi(query, max_results_per_query=4):
    """
    Runs several rewritten query variants, merges the results, strips out
    known noise domains (social/video sites), removes duplicate URLs, and
    ranks trusted domains (.gov, .edu, arxiv.org, ieee.org, vendor sites)
    first.
    """
    seen_urls = set()
    combined = []

    for q in _build_search_queries(query):
        try:
            for r in web_search(q, max_results=max_results_per_query):
                url = r.get("href", "")
                if not url or url in seen_urls:
                    continue
                if _is_bad_domain(r):
                    continue
                seen_urls.add(url)
                combined.append(r)
        except Exception as e:
            print(f"Search failed for query '{q}':", e)

    combined.sort(key=_domain_score, reverse=True)
    return combined


def search_agent(state):

    print("\n===== SEARCH AGENT =====")
    keywords = extract_search_keywords(state["query"])

    print("\n===== SEARCH AGENT =====")
    print("Original Query :", state["query"])
    print("Search Keywords:", keywords)

    try:
        raw_results = web_search_multi(
            keywords,
            max_results_per_query=4
        )
    except Exception as e:
        print("Search failed:", e)
        raw_results = []

    relevant_results = [r for r in raw_results if _is_relevant(state["query"], r)]
    # If filtering wiped everything out (e.g. all results were off-topic),
    # fall back to the raw top results rather than passing nothing at all —
    # but only as a last resort.
    results_to_use = (relevant_results or raw_results)[:5]

    if not results_to_use:
        results_text = "No search results were found for this topic."
        citations = ""
    else:
        results_text = "\n\n".join(
            f"{r.get('title', 'Untitled')}\n"
            f"{r.get('body', '')}\n"
            f"Source: {r.get('href', '')}"
            for r in results_to_use
        )

        citation_list = [
            f"[{i}] {r.get('title', 'Untitled Source')}\n{r.get('href', '')}"
            for i, r in enumerate(results_to_use, start=1)
        ]
        citations = "\n\n".join(citation_list)

    print("\nSearch Results:")
    print(results_text)

    return {
        **state,
        "search_results": results_text,
        "citations": citations
    }


def research_agent(state):

    response = qwen.invoke(f"""
You are a Senior Research Analyst.

Your job is to perform factual research using ONLY the web search results provided.

Topic:
{state["query"]}

Web Search Results:
{state["search_results"]}

If the Web Search Results above say "No search results were found for this
topic", or do not actually relate to the Topic, you MUST NOT invent or guess
any facts. Instead, return exactly this and nothing else:

## Key Concepts
- Insufficient search data was available for this topic.

## Current Trends
- Insufficient search data was available for this topic.

## Challenges
- Insufficient search data was available for this topic.

Otherwise, follow these instructions using ONLY the provided search results:

• Ignore advertisements and duplicate information.
• Extract only factual information. Whenever you mention a fact,
append a citation.

Example

NVIDIA introduced new Physical AI models [2].

AI funding increased significantly [1].

At the end include

## Sources

{state["citations"]}

Return markdown only.
• Do NOT add your own knowledge.
• Organize the findings into:

## Key Concepts
- Three important concepts

## Current Trends
- Two latest developments

## Challenges
- Two major issues

Write professionally.

Maximum 150 words.

Return ONLY the research. Do not include your reasoning or thinking process.
""")

    print("\n===== WEB RESULTS PASSED TO RESEARCH =====")
    print(state["search_results"])

    return {
        **state,
        "research": clean_llm_output(response.content)
    }


def analysis_agent(state):

    response = mistral.invoke(f"""
You are a Senior Business Consultant working for McKinsey.

Analyze the research below.

Research (with citations):

{state["research"]}

Your job is NOT to summarize.

Instead identify:

## Insights
- Three strategic insights

## Opportunities
- Three business opportunities

## Risks
- Three potential risks

Focus on:

• Market impact
• Technology impact
• Business value
• Future scope

Maximum 180 words.

Return ONLY the analysis. Do not include your reasoning or thinking process.
""")

    return {
        **state,
        "analysis": clean_llm_output(response.content)
    }


def review_agent(state):

    response = deepseek.invoke(f"""
You are a Senior Research Reviewer.

Review the analysis critically.

Analysis:

{state["analysis"]}

Evaluate the report under these headings.

## Strengths
- Two points

## Weaknesses
- Two points

## Missing Information
- Two points

## Suggested Improvements
- Two points

Focus on:

• Completeness
• Accuracy
• Practical usefulness
• Missing business aspects

Maximum 180 words.

Return ONLY the review. Do not include your reasoning or thinking process.
""")

    return {
        **state,
        "review": clean_llm_output(response.content)
    }


def metrics_agent(state):

    response = deepseek.invoke(f"""
You are an AI Quality Assessment Agent.

Evaluate the research, analysis and review below as a whole.

Research:
{state["research"]}

Analysis:
{state["analysis"]}

Review:
{state["review"]}

Score this work objectively on a scale of 1-10 for each category below.
Base every score ONLY on the content shown above. Do not estimate or
invent any counts (e.g. number of citations, word counts) — those are
measured separately and are not your responsibility.

Return EXACTLY this format:

Research Coverage: X/10
Factual Consistency: X/10
Citation Quality: X/10
Clarity: X/10
Completeness: X/10
Business Value: X/10
Overall Score: X/10

Overall Verdict:
One short paragraph (2-3 sentences) explaining why these scores were given.

Return ONLY the scores and verdict in that exact format — no markdown
heading/title, no extra commentary, no reasoning or thinking process.
""")

    return {
        **state,
        "metrics": clean_llm_output(response.content)
    }


def report_agent(state):

    response = qwen.invoke(f"""
You are a Professional Research Report Writer.

Prepare a polished report using the Research, Analysis and Review.

Research:

{state["research"]}

Analysis:

{state["analysis"]}

Review:

{state["review"]}

Generate the report.

Whenever possible, retain the citation numbers already present in the research.

Example

Generative AI adoption is accelerating [2].

Cybersecurity automation is improving [4].

At the end create

# References

{state["citations"]}

Return markdown only.
# Executive Summary

Write 3-4 concise sentences.

# Introduction

Explain the topic briefly.

# Key Findings

• Three bullet points

# Strategic Opportunities

• Three bullet points

# Risk Assessment

• Three bullet points

# Recommendations

• Three bullet points

# Conclusion

Summarize the overall importance of the topic in 2-3 sentences.

Write professionally.

Use Markdown formatting.

Keep the report between 250 and 350 words.

Return ONLY the report. Do not include your reasoning or thinking process.
""")

    return {
        **state,
        "report": clean_llm_output(response.content)
    }


workflow = StateGraph(AgentState)

workflow.add_node("search", search_agent)
workflow.add_node("research", research_agent)
workflow.add_node("analysis", analysis_agent)
workflow.add_node("review", review_agent)
workflow.add_node("metrics", metrics_agent)
workflow.add_node("report", report_agent)

workflow.set_entry_point("search")

workflow.add_edge("search", "research")
workflow.add_edge("research", "analysis")
workflow.add_edge("analysis", "review")
workflow.add_edge("review", "metrics")
workflow.add_edge("metrics", "report")
workflow.add_edge("report", END)

app = workflow.compile()


def calculate_quality_metrics(report: str) -> dict:
    """
    Objective, programmatically computed quality metrics based on measurable
    properties of the generated report. These are factual counts, not LLM
    guesses — word count, heading structure, citation density, etc.
    Each of the five criteria is worth 20 points, giving a max of 100.
    """
    words         = len(report.split())
    headings      = len(re.findall(r"^#+ .+", report, flags=re.MULTILINE))
    bullet_points = len(re.findall(r"^[•*\-] .+", report, flags=re.MULTILINE))
    citations     = len(re.findall(r"\[\d+\]", report))
    has_refs      = bool(re.search(r"references", report, re.IGNORECASE))

    # Score breakdown — each criterion worth 20 pts (total 100)
    structure_score  = 20 if headings      >= 6  else round(headings / 6 * 20)
    length_score     = 20 if words         >= 250 else round(words / 250 * 20)
    bullets_score    = 20 if bullet_points >= 10  else round(bullet_points / 10 * 20)
    citation_score   = 20 if citations     >= 5   else round(citations / 5 * 20)
    reference_score  = 20 if has_refs             else 0

    overall = structure_score + length_score + bullets_score + citation_score + reference_score

    return {
        "overall":         overall,
        "word_count":      words,
        "headings":        headings,
        "bullet_points":   bullet_points,
        "citations":       citations,
        "has_references":  has_refs,
        # per-dimension breakdown for the table
        "structure_score": structure_score,
        "length_score":    length_score,
        "bullets_score":   bullets_score,
        "citation_score":  citation_score,
        "reference_score": reference_score,
    }


def generate_report(query):
    result = app.invoke({
        "query": query,
        "search_results": "",
        "citations": "",
        "research": "",
        "analysis": "",
        "review": "",
        "metrics": "",
        "report": ""
    })

    report = result["report"]

    # Safety net — only append References if the model dropped them.
    if "references" not in report.lower():
        report += f"\n\n## References\n\n{result['citations']}"

    # Compute objective quality metrics from the finished report.
    quality_metrics = calculate_quality_metrics(report)

    # --------------------------
    # Save report automatically
    # --------------------------
    os.makedirs("history", exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    safe_query = "".join(
        c if c.isalnum() else "_"
        for c in query
    )

    filename = f"history/{safe_query}_{timestamp}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Topic\n\n{query}\n\n")
        f.write(report)

    return {
        "report":         report,
        "search_results": result["search_results"],
        "metrics":        quality_metrics,
    }

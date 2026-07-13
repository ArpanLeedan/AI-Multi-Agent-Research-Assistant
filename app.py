import gradio as gr
from backend import generate_report
from pdf_export import export_pdf
from docx_export import export_docx
import glob
import os


def format_search_results(raw_text):
    """
    Converts the backend's raw search_results text (title / body / Source: url
    blocks separated by blank lines) into a readable bulleted markdown list.
    """
    if not raw_text or not raw_text.strip():
        return "_No search results available._"

    blocks = raw_text.strip().split("\n\n")
    lines = []

    for block in blocks:
        parts = [p for p in block.split("\n") if p.strip()]
        if not parts:
            continue

        title = parts[0].strip()
        source = ""
        body_parts = []

        for p in parts[1:]:
            if p.strip().startswith("Source:"):
                source = p.split("Source:", 1)[1].strip()
            else:
                body_parts.append(p.strip())

        entry = f"- **{title}**"
        if body_parts:
            entry += f"  \n  {' '.join(body_parts)}"
        if source:
            entry += f"  \n  🔗 {source}"

        lines.append(entry)

    return "\n\n".join(lines)


def load_history(filepath):
    if filepath is None:
        return "", "", "", None, None

    with open(filepath, "r", encoding="utf-8") as f:
        report = f.read()

    # Reconstruct a topic name from the filename (used as the title for
    # the regenerated PDF/DOCX). Adjust this if your history filenames
    # don't already contain the topic.
    base = os.path.splitext(os.path.basename(filepath))[0]
    topic = base.replace("_", " ").replace("-", " ").strip()

    pdf_path = export_pdf(topic, report)
    docx_path = export_docx(topic, report)

    return (
        f"📖 Loaded report: **{topic}**",
        report,
        "_Quality metrics are only available for newly generated reports._",
        "_Search results aren't stored with history — only available for newly generated reports._",
        pdf_path,
        docx_path
    )


def format_quality_metrics(metrics: dict) -> str:
    """
    Turns the dict from calculate_quality_metrics() into a Markdown table
    with a per-dimension breakdown and an overall score, presented as a
    proper research-tool quality card rather than a flat number.
    """
    score_bar = "🟩" * (metrics["overall"] // 20) + "⬜" * (5 - metrics["overall"] // 20)

    return f"""### 📊 Report Quality Metrics

| Quality Dimension | Score |
|---|---|
| 📐 Structure (headings) | {metrics['structure_score']}/20 |
| 📝 Length (word count) | {metrics['length_score']}/20 |
| • Bullet Point Coverage | {metrics['bullets_score']}/20 |
| 🔗 Citation Density | {metrics['citation_score']}/20 |
| 📚 References Section | {metrics['reference_score']}/20 |
| **🏆 Overall Score** | **{metrics['overall']}/100** |

{score_bar}

| Metric | Value |
|---|---|
| Word Count | {metrics['word_count']} words |
| Sections / Headings | {metrics['headings']} |
| Bullet Points | {metrics['bullet_points']} |
| Inline Citations | {metrics['citations']} |
| References Included | {"✅ Yes" if metrics['has_references'] else "❌ No"} |
"""


def refresh_history():
    files = sorted(glob.glob("history/*.md"), reverse=True)
    return gr.update(
        choices=files,
        value=files[0] if files else None
    )


# -----------------------------------------
# Generate Function (generator -> two UI states)
# -----------------------------------------
def gradio_generate(topic):

    if not topic.strip():
        yield (
            "⚠️ Please enter a research topic.",
            "",
            "",
            "",
            None,
            None,
            refresh_history(),
            gr.update(visible=False),
            gr.update(interactive=True)
        )
        return

    # --- Step 1: show the loading animation immediately, lock the button ---
    yield (
        "",
        "",
        "",
        "",
        None,
        None,
        gr.update(),
        gr.update(visible=True),
        gr.update(interactive=False)
    )

    # --- Step 2: run the (slow) report generation + exports ---
    result = generate_report(topic)
    report = result["report"]
    search_results = format_search_results(result["search_results"])
    quality = format_quality_metrics(result["metrics"])

    pdf_path = export_pdf(topic, report)
    docx_path = export_docx(topic, report)

    # --- Step 3: hide the animation, show results, refresh history list ---
    yield (
        f"✅ Research report generated successfully for **{topic}**",
        report,
        quality,
        search_results,
        pdf_path,
        docx_path,
        refresh_history(),
        gr.update(visible=False),
        gr.update(interactive=True)
    )


def gradio_clear():
    return (
        "",                          # topic textbox
        "",                          # status
        "",                          # report output
        "",                          # quality metrics
        "",                          # search results
        None,                        # pdf
        None,                        # docx
        gr.update(value=None),       # history dropdown
        gr.update(visible=False),    # loading animation
        gr.update(interactive=True)  # enable button
    )


# -----------------------------------------
# Custom CSS
# -----------------------------------------
custom_css = """
.gradio-container{
    max-width:1100px !important;
    margin:auto;
}

.loader-card{
    background:#f8fafc;
    border:1px solid #dbeafe;
    border-radius:15px;
    padding:20px;
    margin-bottom:20px;
}

.loader-title{
    text-align:center;
    font-size:22px;
    font-weight:bold;
    color:#2563eb;
}

.loader-sub{
    text-align:center;
    color:#6b7280;
    margin-top:8px;
}

/* ---------------- Generating animation ---------------- */
.generating-card{
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    background:#eff6ff;
    border:1px solid #bfdbfe;
    border-radius:15px;
    padding:32px 20px;
    margin-bottom:20px;
}

.spinner{
    width:46px;
    height:46px;
    border:5px solid #dbeafe;
    border-top:5px solid #2563eb;
    border-radius:50%;
    animation:spin 0.9s linear infinite;
    margin-bottom:14px;
}

@keyframes spin{
    0%{ transform:rotate(0deg); }
    100%{ transform:rotate(360deg); }
}

.generating-title{
    font-size:18px;
    font-weight:bold;
    color:#2563eb;
}

.generating-sub{
    color:#6b7280;
    margin-top:6px;
    text-align:center;
}

.generating-dots span{
    animation: blink 1.4s infinite;
    animation-fill-mode: both;
}
.generating-dots span:nth-child(2){ animation-delay:0.2s; }
.generating-dots span:nth-child(3){ animation-delay:0.4s; }

@keyframes blink{
    0%, 80%, 100%{ opacity:0; }
    40%{ opacity:1; }
}

/* ---------------- Theme toggle row ---------------- */
.theme-toggle-row{
    display:flex;
    justify-content:flex-end;
}

/* ---------------- Dark mode ---------------- */
body.dark{
    background:#111827 !important;
    color:white !important;
}

body.dark .gradio-container{
    background:#111827 !important;
}

body.dark textarea{
    background:#1f2937 !important;
    color:white !important;
}

body.dark input{
    background:#1f2937 !important;
    color:white !important;
}

body.dark button{
    background:#374151 !important;
    color:white !important;
}

body.dark .block{
    background:#1f2937 !important;
    border-color:#374151 !important;
}

body.dark label{
    color:#e5e7eb !important;
}

body.dark .markdown, body.dark .prose{
    color:white !important;
}

body.dark .loader-card{
    background:#1f2937;
    border:1px solid #374151;
}

body.dark .loader-title{
    color:#60a5fa;
}

body.dark .loader-sub{
    color:#9ca3af;
}

body.dark .generating-card{
    background:#1f2937;
    border:1px solid #374151;
}

body.dark .generating-title{
    color:#60a5fa;
}

body.dark .generating-sub{
    color:#9ca3af;
}
"""

# -----------------------------------------
# UI
# -----------------------------------------
with gr.Blocks(
    theme=gr.themes.Soft(),
    css=custom_css,
    title="AI Multi-Agent Research Assistant"
) as demo:

    gr.Markdown("""
    # 🤖 AI Multi-Agent Research Assistant
    ### Powered by **LangGraph • Ollama • Qwen3**
    Generate professional research reports using a **Multi-Agent AI Workflow**.
    """)

    with gr.Row(elem_classes="theme-toggle-row"):
        theme_toggle = gr.Button("🌙 Dark Mode", size="sm", scale=0)

    ready_card = gr.HTML("""
    <div class="loader-card">
        <div class="loader-title">
            AI Research Assistant Ready
        </div>
        <div class="loader-sub">
            Enter a research topic and click Generate Research Report.
            Generation usually takes 2–3 minutes.
        </div>
    </div>
    """)

    # Hidden by default. Becomes visible the moment "Generate" is clicked,
    # and hides itself again once the report finishes generating.
    # Using gr.Group (not gr.HTML) for the visibility toggle — Group
    # visibility updates reliably from a generator in Gradio 6.x, whereas
    # toggling visible= directly on an HTML component is not.
    loading_box = gr.Group(visible=False)
    with loading_box:
        gr.HTML(
            """
            <div class="generating-card">
                <div class="spinner"></div>
                <div class="generating-title">
                    Generating your research report
                    <span class="generating-dots"><span>.</span><span>.</span><span>.</span></span>
                </div>
                <div class="generating-sub">
                    Multiple agents are researching, drafting and refining your report.<br>
                    This usually takes 2–3 minutes — please don't close this tab.
                </div>
            </div>
            """
        )

    topic = gr.Textbox(
        label="📌 Research Topic",
        placeholder="Example: Impact of Generative AI on Banking",
        lines=2
    )

    with gr.Row():
        generate_btn = gr.Button(
            "📄 Generate Research Report",
            variant="primary"
        )
        clear_btn = gr.Button("🗑 Clear")

    status = gr.Markdown()

    output = gr.Markdown(label="📄 Generated Report")

    quality_output = gr.Markdown(label="📊 Report Quality Metrics")

    with gr.Accordion("🌐 Web Search Results", open=False):
        search_results_box = gr.Markdown()

    with gr.Row():
        pdf_download = gr.File(label="📄 Download PDF")
        docx_download = gr.File(label="📝 Download DOCX")

    with gr.Accordion("📚 Report History", open=False):
        history_files = sorted(glob.glob("history/*.md"), reverse=True)

        history = gr.Dropdown(
            choices=history_files,
            label="📚 Previously Generated Reports",
            interactive=True
        )

        load_btn = gr.Button("📖 Load Selected Report")

    with gr.Accordion("💡 Example Research Topics", open=False):
        gr.Examples(
            examples=[
                ["Impact of Generative AI on Banking"],
                ["Artificial Intelligence in Healthcare"],
                ["Future of Quantum Computing"],
                ["Blockchain in Supply Chain"],
                ["Cybersecurity using AI"],
                ["Climate Change Technologies"],
                ["Electric Vehicles in India"],
                ["Future of Space Exploration"],
                ["Machine Learning in Agriculture"],
                ["Edge AI for IoT Devices"]
            ],
            inputs=topic
        )

    generate_btn.click(
        fn=gradio_generate,
        inputs=topic,
        outputs=[
            status,
            output,
            quality_output,
            search_results_box,
            pdf_download,
            docx_download,
            history,
            loading_box,
            generate_btn
        ],
        show_progress="hidden"   # we have our own custom loading panel
    )

    theme_toggle.click(
        fn=None,
        inputs=None,
        outputs=theme_toggle,
        js="""
        () => {
            const isDark = document.body.classList.toggle("dark");
            return isDark ? "☀️ Light Mode" : "🌙 Dark Mode";
        }
        """
    )

    load_btn.click(
        fn=load_history,
        inputs=history,
        outputs=[status, output, quality_output, search_results_box, pdf_download, docx_download]
    )

    clear_btn.click(
        fn=gradio_clear,
        outputs=[
            topic,
            status,
            output,
            quality_output,
            search_results_box,
            pdf_download,
            docx_download,
            history,
            loading_box,
            generate_btn
        ]
    )

# queue() is required so the generator's intermediate yield (the loading
# animation) actually streams to the browser instead of being skipped
# straight to the final result.
demo.queue()
demo.launch()

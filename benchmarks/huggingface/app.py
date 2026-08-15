from pathlib import Path

import gradio as gr

from analyze import compare


def run_analysis(baseline: str | None, alpha: str | None, rates: str | None):
    if not baseline or not alpha:
        return {"error": "Upload both an Omega baseline trace and an Alpha trace."}
    try:
        return compare(
            Path(baseline),
            Path(alpha),
            Path(rates) if rates else None,
        )
    except Exception as exc:
        return {"error": str(exc)}


with gr.Blocks(title="AlphaClaw Benchmark Lab") as demo:
    gr.Markdown(
        "# 🦀 AlphaClaw Benchmark Lab\n"
        "A deliberately boring trace comparator. No agent runs here and no model API is called."
    )
    with gr.Row():
        baseline = gr.File(label="Omega baseline (.jsonl)", type="filepath")
        alpha = gr.File(label="Alpha treatment (.jsonl)", type="filepath")
    rates = gr.File(label="Optional explicit rate card (.json)", type="filepath")
    run = gr.Button("Compare")
    report = gr.JSON(label="Report")
    run.click(run_analysis, inputs=[baseline, alpha, rates], outputs=report)


demo.launch(server_name="0.0.0.0", server_port=7860)

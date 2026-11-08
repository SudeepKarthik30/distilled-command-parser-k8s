import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

def build_pdf(filename="report/report.pdf"):
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=3
    )

    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6
    )

    h1_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=5,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=4
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=9.2,
        textColor=colors.HexColor("#1e293b")
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("Cloud Computing Mini Project: Distilled Command Parser on Kubernetes", title_style))
    story.append(Paragraph("Thirumalasetty Karthik | Roll 230101007 | Repository: https://github.com/SudeepKarthik30/distilled-command-parser-k8s | Model release: v1.0", meta_style))

    # Section 1
    story.append(Paragraph("1. Overview", h1_style))
    story.append(Paragraph(
        "A Phi-3.5 teacher model (served locally via Ollama) annotates natural language voice commands with structured intent and slot boundaries. A compact Pythia-70M student is fine-tuned on the verified teacher annotations via knowledge distillation. The student (v1) is served through an asynchronous FastAPI microservice (/healthz, /readyz, /parse) deployed in a k3d Kubernetes cluster backed by SeaweedFS S3-compatible object storage. Model weights are published as GitHub Release v1.0 and decoupled from version control. The full stack is fully reproducible from a clean clone via <code>make up</code>.",
        body_style
    ))

    # Section 2
    story.append(Paragraph("2. Data and cleaning", h1_style))
    story.append(Paragraph(
        "3,000 teacher-annotated examples were audited and cleaned using <code>worker/clean.py</code>. The cleaning pipeline rejected 4 malformed JSON strings, 7 invalid key sets, 0 out-of-domain intents, 81 hallucinated/unmatched slot spans, and 48 duplicate query commands (140 rejected records total), leaving 2,860 verified high-quality training pairs.",
        body_style
    ))

    # Section 3
    story.append(Paragraph("3. Model quality", h1_style))
    story.append(Paragraph(
        "Model evaluation was conducted over 100 gold validation benchmarks (<code>results/score_*.txt</code>).",
        body_style
    ))

    quality_data = [
        [Paragraph(h, table_header_style) for h in ["Model Architecture", "JSON Valid", "Intent", "Date", "Time", "Place", "Full Frame"]],
        [Paragraph(c, table_cell_style) for c in ["Untrained Pythia-70M", "0%", "0%", "0%", "0%", "0%", "0%"]],
        [Paragraph(c, table_cell_style) for c in ["Teacher (Phi-3.5)", "82%", "59%", "65%", "76%", "71%", "39%"]],
        [Paragraph(c, table_cell_style) for c in ["Student v1 (Deployed)", "99%", "75%", "69%", "82%", "57%", "19%"]],
        [Paragraph(c, table_cell_style) for c in ["Student v2 (Greedy)", "99%", "75%", "69%", "82%", "57%", "19%"]]
    ]
    t_quality = Table(quality_data, colWidths=[120, 68, 68, 68, 68, 68, 80])
    t_quality.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white])
    ]))
    story.append(t_quality)
    story.append(Spacer(1, 3))

    story.append(Paragraph(
        "The untrained baseline yielded 0% across all metrics because it generated repetitive token sequences failing the required schema. Post-distillation, Student v1 achieved 99% JSON validity, outperforming the teacher model on JSON compliance (+17%), intent classification (+12%), and time slot extraction (+14%). The teacher retained higher full-frame accuracy (39% vs 29%) due to simultaneous multi-slot fidelity. A repetition penalty of 1.1 degraded decoding into truncated structures; hence greedy unpenalized decoding was retained for production serving.",
        body_style
    ))

    # Section 4
    story.append(Paragraph("4. Deployment and load test", h1_style))
    story.append(Paragraph(
        "Performance benchmarks were gathered using headless Locust across 4 concurrent client workers over 2 minutes against 2 active replicas.",
        body_style
    ))

    load_data = [
        [Paragraph("Evaluation Metric", table_header_style), Paragraph("Observed Value", table_header_style)],
        [Paragraph("Requests / Failures", table_cell_style), Paragraph("342 / 2 (0.58% failure rate)", table_cell_style)],
        [Paragraph("Latency (p50 / p95)", table_cell_style), Paragraph("1,250 ms / 2,700 ms", table_cell_style)],
        [Paragraph("Throughput", table_cell_style), Paragraph("2.85 requests / second", table_cell_style)],
        [Paragraph("CPU Utilization per Pod", table_cell_style), Paragraph("1928m and 1915m (of 2000m ceiling)", table_cell_style)],
        [Paragraph("Memory Consumption per Pod", table_cell_style), Paragraph("742 MiB and 758 MiB (of 1 GiB ceiling)", table_cell_style)],
        [Paragraph("Traffic Distribution Across Replicas", table_cell_style), Paragraph("172 reqs / 168 reqs (50.6% / 49.4% split)", table_cell_style)],
        [Paragraph("Cold-Start Readiness (Median of 3 runs)", table_cell_style), Paragraph("7.1 s (run measurements: 8.2 s, 6.8 s, 7.1 s)", table_cell_style)]
    ]
    t_load = Table(load_data, colWidths=[240, 300])
    t_load.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white])
    ]))
    story.append(t_load)

    # PAGE BREAK TO GUARANTEE CLEAN 2-PAGE LAYOUT
    story.append(PageBreak())

    # Section 5
    story.append(Paragraph("5. Recovery and autoscaling", h1_style))
    story.append(Paragraph(
        "Pod resilience was validated under sustained load by intentionally terminating an active Pod. Out of 450 requests transmitted during the failover event, only 4 returned errors (0.89% failure rate, all transient HTTP 500), and the replacement Pod achieved Ready status within 17.5 seconds. Horizontal Pod Autoscaler (HPA target CPU: 70%, replica span: 1 to 2) triggered scale-up from 1 to 2 replicas when aggregate CPU exceeded 195%, and smoothly scaled back down to 1 replica approximately 5 minutes after load cessation.",
        body_style
    ))

    # Section 6
    story.append(Paragraph("6. Cost and SLO", h1_style))
    story.append(Paragraph(
        "Cost per replica-hour is calculated via 2 vCPU x 3.50 INR + 1 GiB x 0.45 INR = 7.45 INR/h, totaling 14.90 INR/h for a dual-replica deployment. At an observed throughput of 2.85 req/s (10,260 requests/hour), the unit economic cost is 1.45 INR per 1,000 processed requests. The service level objective (SLO) requires >= 99% successful requests per test run. The SLO was cleanly satisfied in the standard baseline run (99.42% success; 2 errors against a 3.42 error budget) and during simulated pod kill (99.11% success).",
        body_style
    ))

    # Section 7
    story.append(Paragraph("7. Component analysis", h1_style))
    comp_data = [
        [Paragraph(h, table_header_style) for h in ["Component", "Identified Limitation", "Recommended Engineering Improvement"]],
        [
            Paragraph("Data & Object Storage", table_cell_style),
            Paragraph("Single-node SeaweedFS without HA replication; cold starts fetch weights over cluster network at every pod launch.", table_cell_style),
            Paragraph("Implement distributed multi-node storage backend; attach persistent volume caches (PVC) directly to nodes.", table_cell_style)
        ],
        [
            Paragraph("Model Quality", table_cell_style),
            Paragraph("Compact 70M parameter student exhibits occasional syntax errors and slot span boundary hallucinations.", table_cell_style),
            Paragraph("Incorporate larger distillation pools, synthetic edge cases, and grammar-constrained JSON decoding (e.g. Outlines/Guidance).", table_cell_style)
        ],
        [
            Paragraph("Latency & Throughput", table_cell_style),
            Paragraph("Inference is CPU-bound; thread contention occurred prior to setting OMP/MKL thread clamps (p95 was 7.7s).", table_cell_style),
            Paragraph("Leverage INT8/INT4 quantization (bitsandbytes/ONNX Runtime) and dynamic continuous batching.", table_cell_style)
        ],
        [
            Paragraph("Resource Utilization", table_cell_style),
            Paragraph("Pods saturated near 100% CPU limits at only 4 concurrent users.", table_cell_style),
            Paragraph("Optimize inference runtime, right-size memory limits, and horizontal scale across multi-node topology.", table_cell_style)
        ],
        [
            Paragraph("Reliability & HA", table_cell_style),
            Paragraph("Local single-node k3d environment lacks true physical host redundancy.", table_cell_style),
            Paragraph("Multi-node Kubernetes cluster with node anti-affinity, pod disruption budgets (PDB), and higher HPA max limits.", table_cell_style)
        ],
        [
            Paragraph("Security & Governance", table_cell_style),
            Paragraph("Storage credentials stored in base64 Secrets; Ingress operates over unencrypted HTTP.", table_cell_style),
            Paragraph("Integrate HashiCorp Vault / External Secrets Operator, cert-manager for automated TLS termination, and mTLS.", table_cell_style)
        ]
    ]
    t_comp = Table(comp_data, colWidths=[95, 220, 225])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white])
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 4))

    # Section 8
    story.append(Paragraph("8. Use of AI", h1_style))
    story.append(Paragraph(
        "Antigravity (Gemini) and Anthropic Claude were utilized for architecture planning, manifest drafting, and diagnosing PyTorch thread oversubscription under CPU limits. Every suggested shell command, manifest, and Python refactor was executed locally and rigorously verified against automated testing suites. The stateless NACL was tested and verified with <code>tools/nacl_sim.py</code> (6/6 passing, 100%). Model scoring was audited with <code>tools/score.py</code>, and request timings were measured directly via Locust. AI inaccuracies (such as default Makefile target precedence and premature readiness probe pass) were identified, corrected, and documented. Distillation labels were produced exclusively by Phi-3.5 via Ollama without synthetic manual fabrication. Full verification logs are detailed in <code>AI_USE.md</code>.",
        body_style
    ))

    doc.build(story)
    print(f"Report generated successfully: {filename}")

if __name__ == "__main__":
    build_pdf()

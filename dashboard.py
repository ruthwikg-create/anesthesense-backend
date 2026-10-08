import hashlib
import io
import json
import time

import plotly.graph_objects as go
import requests
import streamlit as st

from patient_replay import parse_csv_bytes


# ---------------------------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AnestheSense | Hemodynamic Intelligence",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# DESIGN SYSTEM
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --bg: #071018;
        --panel: #0d1721;
        --panel-2: #101d29;
        --border: #223344;
        --text: #e8f0f7;
        --muted: #8fa2b5;
        --cyan: #36c9d7;
        --green: #37d39b;
        --amber: #f2b84b;
        --red: #ff5d67;
    }

    html, body, [class*="css"] {
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
    }

    .block-container {
        max-width: 1480px;
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"] {
        background: #08121b;
        border-right: 1px solid var(--border);
    }

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        border: 1px solid var(--border);
        border-radius: 16px;
        background: linear-gradient(135deg, #0d1924 0%, #0a141d 100%);
        margin-bottom: 18px;
    }

    .brand {
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: .02em;
    }

    .brand span {
        color: var(--cyan);
    }

    .subtitle {
        color: var(--muted);
        font-size: .78rem;
        margin-top: 2px;
    }

    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 7px 12px;
        border-radius: 999px;
        border: 1px solid #284052;
        background: #0b1822;
        color: #b9c9d6;
        font-size: .78rem;
        font-weight: 700;
    }

    .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        background: var(--green);
        box-shadow: 0 0 10px rgba(55, 211, 155, .6);
    }

    .section-label {
        color: var(--cyan);
        font-size: .72rem;
        font-weight: 800;
        letter-spacing: .13em;
        text-transform: uppercase;
        margin: 4px 0 8px;
    }

    .hero {
        padding: 28px;
        border: 1px solid var(--border);
        border-radius: 20px;
        background:
            radial-gradient(circle at 90% 10%, rgba(54, 201, 215, .13), transparent 35%),
            linear-gradient(145deg, #0e1b26, #09131c);
        margin-bottom: 18px;
    }

    .hero h1 {
        margin: 0 0 7px;
        font-size: 2rem;
        letter-spacing: -.03em;
    }

    .hero p {
        color: var(--muted);
        max-width: 800px;
        margin: 0;
        line-height: 1.6;
    }

    .stage-card {
        min-height: 145px;
        padding: 20px;
        border: 1px solid var(--border);
        border-radius: 18px;
        background: var(--panel);
    }

    .stage-card.active {
        border-color: rgba(54, 201, 215, .65);
        box-shadow: 0 0 0 1px rgba(54, 201, 215, .08);
    }

    .stage-number {
        color: var(--cyan);
        font-size: .72rem;
        font-weight: 800;
        letter-spacing: .1em;
    }

    .stage-title {
        font-size: 1rem;
        font-weight: 800;
        margin-top: 9px;
    }

    .stage-copy {
        color: var(--muted);
        font-size: .78rem;
        line-height: 1.45;
        margin-top: 6px;
    }

    .metric-card {
        padding: 18px;
        border: 1px solid var(--border);
        border-radius: 16px;
        background: var(--panel);
        min-height: 112px;
    }

    .metric-label {
        color: var(--muted);
        font-size: .74rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .08em;
    }

    .metric-value {
        font-size: 1.75rem;
        font-weight: 800;
        margin-top: 7px;
    }

    .metric-delta {
        color: var(--muted);
        font-size: .74rem;
        margin-top: 5px;
    }

    .risk-critical {
        border-color: rgba(255, 93, 103, .65);
        background: linear-gradient(135deg, rgba(255, 93, 103, .14), #10161e);
    }

    .risk-high {
        border-color: rgba(242, 184, 75, .65);
        background: linear-gradient(135deg, rgba(242, 184, 75, .12), #10161e);
    }

    .risk-moderate {
        border-color: rgba(242, 184, 75, .45);
    }

    .risk-low {
        border-color: rgba(55, 211, 155, .45);
    }

    .alert-banner {
        padding: 18px 20px;
        border-radius: 16px;
        border: 1px solid rgba(255, 93, 103, .55);
        background: rgba(255, 93, 103, .10);
        margin: 14px 0 18px;
    }

    .alert-title {
        color: #ff8b91;
        font-weight: 800;
        font-size: 1rem;
    }

    .alert-copy {
        color: #c9d4dd;
        font-size: .82rem;
        margin-top: 5px;
    }

    .good-banner {
        padding: 16px 18px;
        border-radius: 16px;
        border: 1px solid rgba(55, 211, 155, .45);
        background: rgba(55, 211, 155, .08);
        margin: 14px 0 18px;
    }

    .info-box {
        padding: 18px;
        border: 1px solid var(--border);
        border-radius: 16px;
        background: var(--panel);
        line-height: 1.6;
    }

    .timeline-item {
        border-left: 2px solid #2a4355;
        padding: 0 0 18px 18px;
        margin-left: 8px;
        color: #c9d5df;
        font-size: .82rem;
    }

    .timeline-item:last-child {
        border-left-color: transparent;
    }

    .timeline-dot {
        width: 8px;
        height: 8px;
        background: var(--cyan);
        border-radius: 50%;
        display: inline-block;
        margin-left: -24px;
        margin-right: 12px;
    }

    .footer-note {
        color: #687d8e;
        font-size: .72rem;
        text-align: center;
        margin-top: 28px;
        padding-top: 16px;
        border-top: 1px solid var(--border);
    }

    .stButton > button {
        border-radius: 10px;
        font-weight: 700;
        min-height: 42px;
    }

    div[data-testid="stFileUploader"] {
        border: 1px dashed #365064;
        border-radius: 16px;
        padding: 8px;
        background: rgba(13, 23, 33, .65);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------

DEFAULTS = {
    "stage": "case",
    "case_id": "OR-07",
    "patient_id": "DEMO-001",
    "procedure": "General Surgery",
    "data_source": "Synthetic simulation",
    "scenario": "Hypovolemia",
    "telemetry": None,
    "csv_report": None,
    "prediction": None,
    "predictions": [],
    "case_started": False,
    "monitoring_complete": False,
    "alert_acknowledged": False,
    "csv_bytes": None,
    "csv_filename": None,
    "csv_sha256": None,
    "csv_error": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

STAGES = [
    ("01", "Case", "Create or select the case."),
    ("02", "Data", "Import or generate telemetry."),
    ("03", "Verify", "Confirm signal integrity."),
    ("04", "Monitor", "Process the physiological trajectory."),
    ("05", "Analysis", "Review forecast and risk."),
    ("06", "Report", "Summarize and export the case."),
]

SCENARIOS = [
    "Vasodilation",
    "Hypovolemia",
    "Hemorrhage",
    "MixedShock",
    "HypoxiaStress",
    "Normotensive",
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def api_url():
    return st.session_state.get("api_url", "http://127.0.0.1:8000").rstrip("/")


def post_predict(payload):
    """Call the prediction API and surface actionable errors without crashing the UI."""
    try:
        response = requests.post(
            f"{api_url()}/api/v1/predict",
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise requests.RequestException(
            f"Cannot reach AnestheSense backend at {api_url()}. "
            f"Start FastAPI first. Details: {exc}"
        ) from exc

    if response.ok:
        return response.json()

    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text

    raise requests.HTTPError(
        f"Backend returned HTTP {response.status_code}: {detail}",
        response=response,
    )


def risk_class(level):
    return {
        "CRITICAL": "risk-critical",
        "HIGH": "risk-high",
        "MODERATE": "risk-moderate",
        "LOW": "risk-low",
    }.get(level, "")


def stage_index():
    names = [item[1].lower() for item in STAGES]
    return names.index(st.session_state.stage.lower())


def go_to(stage):
    st.session_state.stage = stage
    st.rerun()


def metric_card(label, value, detail="", extra_class=""):
    st.markdown(
        f"""
        <div class="metric-card {extra_class}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-delta">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_topbar():
    case = st.session_state.case_id
    status = "MONITORING" if st.session_state.case_started else "READY"

    st.markdown(
        f"""
        <div class="topbar">
            <div>
                <div class="brand">Anesthe<span>Sense</span></div>
                <div class="subtitle">Intraoperative Hemodynamic Intelligence</div>
            </div>
            <div>
                <span class="status-pill">
                    <span class="dot"></span>
                    {status}
                </span>
                <span style="margin-left:10px;color:#8fa2b5;font-size:.78rem;">
                    CASE {case}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_progress():
    current = stage_index()
    cols = st.columns(len(STAGES))

    for index, ((number, title, copy), col) in enumerate(zip(STAGES, cols)):
        active = "active" if index == current else ""
        completed = "✓" if index < current else number

        with col:
            st.markdown(
                f"""
                <div class="stage-card {active}">
                    <div class="stage-number">{completed}</div>
                    <div class="stage-title">{title}</div>
                    <div class="stage-copy">{copy}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_footer():
    st.markdown(
        """
        <div class="footer-note">
            AnestheSense is a research/demo clinical decision-support prototype.
            It is not clinically validated and must not be used to direct patient care.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_plot(observed, predicted10=None, predicted15=None, title="Hemodynamic trajectory", key="trajectory"):
    fig = go.Figure()

    x_observed = list(range(-len(observed) + 1, 1))

    fig.add_trace(
        go.Scatter(
            x=x_observed,
            y=observed,
            mode="lines+markers",
            name="Observed MAP",
            line={"width": 3},
        )
    )

    if predicted10 is not None and predicted15 is not None:
        fig.add_trace(
            go.Scatter(
                x=[0, 10, 15],
                y=[observed[-1], predicted10, predicted15],
                mode="lines+markers",
                name="Forecast",
                line={"dash": "dash", "width": 2},
            )
        )

    fig.add_hline(
        y=65,
        line_dash="dot",
        annotation_text="MAP 65",
        annotation_position="top left",
    )
    fig.add_hline(
        y=60,
        line_dash="dot",
        annotation_text="MAP 60",
        annotation_position="bottom left",
    )

    fig.update_layout(
        title=title,
        height=420,
        margin={"l": 15, "r": 15, "t": 55, "b": 25},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#cbd6df"},
        xaxis={
            "title": "Relative time (min)",
            "gridcolor": "#1d2c39",
            "zerolinecolor": "#344b5d",
        },
        yaxis={
            "title": "MAP (mmHg)",
            "gridcolor": "#1d2c39",
            "range": [30, 110],
        },
        legend={"orientation": "h", "y": 1.12},
    )

    st.plotly_chart(fig, use_container_width=True, key=key)


def telemetry_frames():
    return st.session_state.telemetry or []


def current_prediction():
    return st.session_state.prediction


def calculate_future_map(frames, now_minute, horizon):
    target = now_minute + horizon
    candidates = [f for f in frames if f["minute"] >= target]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda f: abs(f["minute"] - target),
    )["MAP"]


def replay_mae(frames, predictions, horizon):
    errors = []

    for item in predictions:
        actual = calculate_future_map(
            frames,
            item["minute"],
            horizon,
        )

        if actual is None:
            continue

        key = f"predicted_map_{horizon}min"
        predicted = item["result"]["features"].get(key)

        if predicted is not None:
            errors.append(abs(predicted - actual))

    return sum(errors) / len(errors) if errors else None


def make_prediction(frames):
    interval = 30.0

    if len(frames) >= 2:
        interval = max(
            0.1,
            (frames[1]["minute"] - frames[0]["minute"]) * 60,
        )

    return post_predict(
        {
            "patient_id": st.session_state.patient_id,
            "sampling_interval_seconds": interval,
            "telemetry": frames,
        }
    )


def import_csv(raw_bytes, filename):
    """Persist and validate CSV bytes across Streamlit reruns."""
    if not raw_bytes:
        st.session_state.csv_error = "The selected CSV file is empty."
        return False

    st.session_state.csv_bytes = bytes(raw_bytes)
    st.session_state.csv_filename = filename or "patient.csv"
    st.session_state.csv_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    st.session_state.csv_error = None

    try:
        telemetry, report = parse_csv_bytes(
            raw_bytes,
            patient_id=st.session_state.patient_id,
        )
        st.session_state.telemetry = [
            frame.model_dump(exclude_none=True)
            for frame in telemetry.telemetry
        ]
        st.session_state.csv_report = report
        return True
    except ValueError as exc:
        st.session_state.csv_error = str(exc)
        st.session_state.csv_report = None
        st.session_state.telemetry = None
        return False


def csv_template():
    return (
        "timestamp,minute,MAP,HR,SVV,EtCO2,SpO2,CVP\n"
        "2026-10-08T10:00:00,0,82,76,9,36,99,7\n"
        "2026-10-08T10:00:30,0.5,79,78,10,35,99,7\n"
        "2026-10-08T10:01:00,1,76,80,12,35,99,7\n"
    )


def normalized_csv():
    output = io.StringIO()
    output.write("minute,MAP,HR,SVV,EtCO2,SpO2,CVP\n")
    for frame in telemetry_frames():
        values = [
            frame.get("minute", ""),
            frame.get("MAP", ""),
            frame.get("HR", ""),
            frame.get("SVV", ""),
            frame.get("EtCO2", ""),
            frame.get("SpO2", ""),
            frame.get("CVP", ""),
        ]
        output.write(",".join("" if value is None else str(value) for value in values))
        output.write("\n")
    return output.getvalue()


def render_csv_import_center():
    st.markdown("### CSV Import Center")
    st.markdown(
        """
        <div class="info-box">
            <strong>Clinical telemetry CSV</strong><br>
            Required: MAP + HR. Optional: SVV, EtCO₂, SpO₂ and CVP.
            Timestamp/minute are optional. UTF-8, UTF-16 and CP1252 files are supported,
            including comma, semicolon, tab and pipe delimiters.
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Drop CSV here or click Browse files",
        type=["csv"],
        accept_multiple_files=False,
        key="persistent_csv_uploader",
        help="The file is persisted in the current case so Streamlit reruns do not lose it.",
    )

    if uploaded is not None:
        raw = uploaded.getvalue()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != st.session_state.csv_sha256:
            import_csv(raw, uploaded.name)

    if st.session_state.csv_error:
        st.error("CSV import failed: " + st.session_state.csv_error)
        st.download_button(
            "DOWNLOAD WORKING CSV TEMPLATE",
            csv_template(),
            "AnestheSense_patient_template.csv",
            "text/csv",
            key="csv_template_error",
        )
        return

    if st.session_state.csv_bytes is None:
        st.caption("No CSV imported yet.")

        demo_col, template_col = st.columns(2)

        with demo_col:
            if st.button(
                "LOAD BUILT-IN DEMO CSV",
                type="secondary",
                use_container_width=True,
                key="load_builtin_demo_csv",
            ):
                rows = ["timestamp,minute,MAP,HR,SVV,EtCO2,SpO2,CVP"]
                for i in range(41):
                    minute = i * 0.5
                    map_value = 88 - (26 * i / 40)
                    hr_value = 72 + (18 * i / 40)
                    svv_value = 9 + (11 * i / 40)
                    etco2_value = 36 - (4 * i / 40)
                    second = 30 if i % 2 else 0
                    rows.append(
                        f"2026-10-08T10:{int(minute):02d}:{second:02d},"
                        f"{minute:.1f},{map_value:.1f},{hr_value:.1f},"
                        f"{svv_value:.1f},{etco2_value:.1f},99,7"
                    )

                import_csv(
                    "\\n".join(rows).encode("utf-8"),
                    "anesthesense_demo_patient.csv",
                )
                st.rerun()

        with template_col:
            st.download_button(
                "DOWNLOAD CSV TEMPLATE",
                csv_template(),
                "AnestheSense_patient_template.csv",
                "text/csv",
                use_container_width=True,
                key="csv_template_empty",
            )

        return

    report = st.session_state.csv_report
    if report is None:
        return

    st.success(
        f"CSV READY · {st.session_state.csv_filename} · "
        f"{report.rows_used} usable frames"
    )
    st.caption(
        f"SHA-256: {st.session_state.csv_sha256} · "
        f"{len(st.session_state.csv_bytes) / 1024:.1f} KB"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows read", report.rows_read)
    c2.metric("Usable frames", report.rows_used)
    c3.metric("Rows skipped", report.rows_skipped)
    c4.metric("Sampling", f"{report.sampling_interval_seconds:.1f} s")

    st.markdown("### Signal mapping")
    mapping_cols = st.columns(6)
    for col, signal in zip(mapping_cols, ["MAP", "HR", "SVV", "EtCO2", "SpO2", "CVP"]):
        with col:
            source = report.mapped_columns.get(signal)
            metric_card(signal, "✓" if source else "—", source or "not supplied")

    if report.missing_optional_signals:
        st.info(
            "Optional signals not present: "
            + ", ".join(report.missing_optional_signals)
            + ". Missing measurements are not fabricated."
        )

    quality = max(
        0,
        min(100, round((report.rows_used / report.rows_read) * 100))
        if report.rows_read
        else 0,
    )
    st.markdown("### Import quality")
    st.progress(quality / 100, text=f"Usable row quality: {quality}%")

    if quality >= 95:
        st.success("IMPORT QUALITY: HIGH")
    elif quality >= 75:
        st.warning("IMPORT QUALITY: REVIEW")
    else:
        st.error("IMPORT QUALITY: POOR")

    with st.expander("Preview imported data", expanded=True):
        st.dataframe(
            telemetry_frames()[:15],
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Detected column mapping"):
        st.json(report.mapped_columns)

    with st.expander("Normalized dataset"):
        st.dataframe(
            telemetry_frames(),
            use_container_width=True,
            hide_index=True,
        )
        st.download_button(
            "DOWNLOAD NORMALIZED CSV",
            normalized_csv(),
            f"{st.session_state.case_id}_normalized.csv",
            "text/csv",
            key="download_normalized_csv",
        )

    left, right = st.columns(2)
    with left:
        if st.button("REPLACE CSV", use_container_width=True, key="replace_csv"):
            st.session_state.csv_bytes = None
            st.session_state.csv_filename = None
            st.session_state.csv_sha256 = None
            st.session_state.csv_report = None
            st.session_state.csv_error = None
            st.session_state.telemetry = None
            st.rerun()

    with right:
        action_left, action_right = st.columns(2)

        with action_left:
            if st.button(
                "VERIFY DATA →",
                type="secondary",
                use_container_width=True,
                key="continue_csv_data",
            ):
                go_to("verify")

        with action_right:
            if st.button(
                "ANALYZE CSV NOW →",
                type="primary",
                use_container_width=True,
                key="analyze_csv_now",
            ):
                if len(telemetry_frames()) >= 2:
                    st.session_state.case_started = True
                    go_to("monitor")
                else:
                    st.error("At least two usable telemetry frames are required.")


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

render_topbar()
render_progress()


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### System configuration")

    st.session_state.api_url = st.text_input(
        "Backend URL",
        value=st.session_state.get("api_url", "http://127.0.0.1:8000"),
    )

    st.markdown("---")
    st.markdown("### Case status")

    st.write(f"**Case:** {st.session_state.case_id}")
    st.write(f"**Patient:** {st.session_state.patient_id}")
    st.write(f"**Source:** {st.session_state.data_source}")

    if st.session_state.telemetry:
        st.write(f"**Frames:** {len(st.session_state.telemetry)}")

    st.markdown("---")
    st.caption("Safety boundary")
    st.info(
        "Deterministic risk severity and alarm state remain authoritative. "
        "Optional generative AI is an explanation layer only. No medication dosing "
        "or autonomous treatment is generated."
    )


# ---------------------------------------------------------------------------
# STAGE 01 — CASE
# ---------------------------------------------------------------------------

if st.session_state.stage == "case":
    st.markdown(
        """
        <div class="hero">
            <div class="section-label">01 / Case setup</div>
            <h1>Start a monitoring case</h1>
            <p>
                Establish the case context first. AnestheSense then moves through
                data acquisition, signal verification, trajectory monitoring,
                explainable analysis, and case reporting.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.3, 1])

    with left:
        st.markdown("### Case information")

        st.session_state.case_id = st.text_input(
            "Case ID",
            st.session_state.case_id,
        )

        st.session_state.patient_id = st.text_input(
            "Patient / Demo ID",
            st.session_state.patient_id,
        )

        st.session_state.procedure = st.selectbox(
            "Procedure context",
            [
                "General Surgery",
                "Orthopedic Surgery",
                "Neurosurgery",
                "Cardiothoracic Surgery",
                "Abdominal Surgery",
                "Other",
            ],
            index=[
                "General Surgery",
                "Orthopedic Surgery",
                "Neurosurgery",
                "Cardiothoracic Surgery",
                "Abdominal Surgery",
                "Other",
            ].index(st.session_state.procedure),
        )

    with right:
        st.markdown("### Data source")

        source = st.radio(
            "Choose how this case will receive data",
            [
                "Synthetic simulation",
                "Patient CSV replay",
                "Manual telemetry",
            ],
            index=[
                "Synthetic simulation",
                "Patient CSV replay",
                "Manual telemetry",
            ].index(st.session_state.data_source),
        )

        st.session_state.data_source = source

        if source == "Synthetic simulation":
            st.session_state.scenario = st.selectbox(
                "Simulation scenario",
                SCENARIOS,
                index=SCENARIOS.index(st.session_state.scenario),
            )

    st.markdown("---")

    if st.button(
        "START NEW CASE →",
        type="primary",
        use_container_width=True,
        key="start_case",
    ):
        st.session_state.case_started = True
        st.session_state.telemetry = None
        st.session_state.csv_report = None
        st.session_state.prediction = None
        st.session_state.predictions = []
        st.session_state.monitoring_complete = False
        st.session_state.alert_acknowledged = False
        st.session_state.csv_bytes = None
        st.session_state.csv_filename = None
        st.session_state.csv_sha256 = None
        st.session_state.csv_error = None
        go_to("data")


# ---------------------------------------------------------------------------
# STAGE 02 — DATA ACQUISITION
# ---------------------------------------------------------------------------

elif st.session_state.stage == "data":
    st.markdown(
        """
        <div class="hero">
            <div class="section-label">02 / Data acquisition</div>
            <h1>Bring the physiological data into the case</h1>
            <p>
                AnestheSense can work with a deterministic simulation, a
                de-identified CSV replay, or manually entered telemetry.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.data_source == "Synthetic simulation":
        st.markdown("### Simulation laboratory")

        st.info(
            f"Scenario selected: **{st.session_state.scenario}**. "
            "The backend generates deterministic synthetic telemetry for reproducible demonstrations."
        )

        if st.button(
            "GENERATE TELEMETRY →",
            type="primary",
            use_container_width=True,
            key="generate_sim",
        ):
            try:
                response = requests.post(
                    f"{api_url()}/api/v1/simulate",
                    json={
                        "patient_id": st.session_state.patient_id,
                        "scenario": st.session_state.scenario,
                        "frames": 31,
                        "interval_seconds": 30,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                st.session_state.telemetry = response.json()["telemetry"]
                st.session_state.prediction = None
                st.success(
                    f"Generated {len(st.session_state.telemetry)} telemetry frames."
                )
            except requests.RequestException as exc:
                st.error(f"Backend connection failed: {exc}")

    elif st.session_state.data_source == "Patient CSV replay":
        render_csv_import_center()

    else:
        st.markdown("### Manual telemetry")

        st.info(
            "Use this mode to stress-test the prediction engine with a controlled "
            "six-frame physiological trajectory."
        )

        map_now = st.slider("MAP (mmHg)", 40, 110, 70, key="manual_map")
        map_slope = st.slider(
            "MAP slope (mmHg/min)",
            -3.0,
            2.0,
            -0.5,
            0.1,
            key="manual_slope",
        )
        hr = st.slider("HR (bpm)", 40, 180, 90, key="manual_hr")
        svv = st.slider("SVV (%)", 0, 35, 12, key="manual_svv")
        etco2 = st.slider("EtCO₂ (mmHg)", 15, 60, 34, key="manual_etco2")
        spo2 = st.slider("SpO₂ (%)", 70, 100, 98, key="manual_spo2")

        st.session_state.telemetry = [
            {
                "minute": i - 5,
                "MAP": round(map_now + map_slope * i, 1),
                "HR": hr,
                "SVV": svv,
                "EtCO2": etco2,
                "SpO2": spo2,
            }
            for i in range(6)
        ]

        st.dataframe(
            st.session_state.telemetry,
            use_container_width=True,
            hide_index=True,
        )

    if st.session_state.telemetry:
        st.markdown("---")

        if st.button(
            "CONTINUE TO SIGNAL VERIFICATION →",
            type="primary",
            use_container_width=True,
            key="data_continue",
        ):
            go_to("verify")


# ---------------------------------------------------------------------------
# STAGE 03 — SIGNAL VERIFICATION
# ---------------------------------------------------------------------------

elif st.session_state.stage == "verify":
    frames = telemetry_frames()

    st.markdown(
        """
        <div class="hero">
            <div class="section-label">03 / Signal verification</div>
            <h1>Verify what the engine received</h1>
            <p>
                The system checks completeness and displays the imported trajectory
                before the prediction workflow begins. Optional signals are never fabricated.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not frames:
        st.warning("No telemetry is available for this case.")
        if st.button("← Return to data acquisition", key="verify_back_empty"):
            go_to("data")
    else:
        latest = frames[-1]

        signal_names = [
            ("MAP", "mmHg", "MAP"),
            ("HR", "bpm", "HR"),
            ("SVV", "%", "SVV"),
            ("EtCO₂", "mmHg", "EtCO2"),
            ("SpO₂", "%", "SpO2"),
            ("CVP", "mmHg", "CVP"),
        ]

        cols = st.columns(6)

        for col, (label, unit, key) in zip(cols, signal_names):
            value = latest.get(key)

            with col:
                if value is None:
                    metric_card(
                        label,
                        "N/A",
                        "not supplied",
                    )
                else:
                    metric_card(
                        label,
                        f"{value:.1f}",
                        unit,
                    )

        st.markdown("### MAP trajectory received")
        render_plot(
            [frame["MAP"] for frame in frames],
            title="Pre-analysis MAP trajectory",
            key="verification_map_chart",
        )

        available = []
        missing = []

        for _, _, key in signal_names:
            if any(frame.get(key) is not None for frame in frames):
                available.append(key)
            else:
                missing.append(key)

        a, b = st.columns(2)

        with a:
            st.markdown("### Available signals")
            for signal in available:
                st.write(f"✓ {signal}")

        with b:
            st.markdown("### Not supplied")
            for signal in missing:
                st.write(f"○ {signal}")

        st.markdown("---")

        back, begin = st.columns(2)

        with back:
            if st.button(
                "← BACK TO DATA",
                use_container_width=True,
                key="verify_back",
            ):
                go_to("data")

        with begin:
            if st.button(
                "BEGIN HEMODYNAMIC MONITORING →",
                type="primary",
                use_container_width=True,
                key="begin_monitoring",
            ):
                go_to("monitor")


# ---------------------------------------------------------------------------
# STAGE 04 — MONITOR
# ---------------------------------------------------------------------------

elif st.session_state.stage == "monitor":
    frames = telemetry_frames()

    st.markdown(
        """
        <div class="hero">
            <div class="section-label">04 / Monitoring</div>
            <h1>Process the hemodynamic trajectory</h1>
            <p>
                The telemetry is replayed through the same prediction endpoint used
                by the API. The latest deterministic assessment becomes the basis
                for the analysis stage.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not frames:
        st.error("No telemetry is available.")
        if st.button("← Return to data"):
            go_to("data")
    else:
        st.markdown("### Monitoring workstation")

        progress = st.progress(0)
        monitor_status = st.empty()
        chart_area = st.empty()
        metrics_area = st.empty()

        predictions = []

        # Replay all available frames when this stage is entered.
        # A minimum of two frames is required by the prediction API.
        for index in range(2, len(frames) + 1):
            prefix = frames[:index]

            try:
                result = make_prediction(prefix)
            except requests.RequestException as exc:
                st.error(f"Backend connection failed: {exc}")
                st.stop()

            predictions.append(
                {
                    "minute": prefix[-1]["minute"],
                    "result": result,
                }
            )

            a = result["clinical_assessment"]
            f = result["features"]

            with metrics_area.container():
                c1, c2, c3, c4 = st.columns(4)

                c1.metric(
                    "Current MAP",
                    f"{f['map_current']:.1f} mmHg",
                )
                c2.metric(
                    "Predicted +15 min",
                    f"{a['predicted_map_15min']:.1f} mmHg",
                )
                c3.metric(
                    "Risk",
                    a["hypotension_risk_level"],
                )
                c4.metric(
                    "Confidence",
                    f"{a['confidence_score']:.0%}",
                )

            with chart_area.container():
                render_plot(
                    [frame["MAP"] for frame in prefix],
                    f["predicted_map_10min"],
                    f["predicted_map_15min"],
                    title=f"Live case trajectory — {st.session_state.case_id}",
                    key=f"monitor_chart_{index}",
                )

            monitor_status.info(
                f"Frame {index}/{len(frames)} · "
                f"{f['trajectory']} · "
                f"{a['suspected_mechanism']}"
            )

            progress.progress(index / len(frames))

            # Fast visual replay; this is not intended to represent real-time physiology.
            time.sleep(0.05)

        st.session_state.prediction = predictions[-1]["result"]
        st.session_state.predictions = predictions
        st.session_state.monitoring_complete = True

        final = st.session_state.prediction
        final_a = final["clinical_assessment"]

        if final["alert_triggered"]:
            st.markdown(
                f"""
                <div class="alert-banner">
                    <div class="alert-title">
                        {final_a["alert_priority"]} ALERT — {final_a["primary_risk"]}
                    </div>
                    <div class="alert-copy">
                        Predicted MAP at +15 min:
                        <strong>{final_a["predicted_map_15min"]:.1f} mmHg</strong>.
                        Clinical review is required.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="good-banner">
                    Monitoring completed without a HIGH/CRITICAL alert.
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.button(
            "CONTINUE TO ANALYSIS →",
            type="primary",
            use_container_width=True,
            key="monitor_continue",
        ):
            go_to("analysis")


# ---------------------------------------------------------------------------
# STAGE 05 — ANALYSIS
# ---------------------------------------------------------------------------

elif st.session_state.stage == "analysis":
    result = current_prediction()
    frames = telemetry_frames()

    st.markdown(
        """
        <div class="hero">
            <div class="section-label">05 / Explainable analysis</div>
            <h1>Understand the predicted trajectory</h1>
            <p>
                AnestheSense separates the deterministic prediction from the
                explanation layer. The assessment below describes why the system
                entered its current state.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result is None:
        st.error("No completed prediction is available.")
        if st.button("← Return to monitoring"):
            go_to("monitor")
    else:
        a = result["clinical_assessment"]
        f = result["features"]
        level = a["hypotension_risk_level"]

        if level in {"CRITICAL", "HIGH"}:
            st.markdown(
                f"""
                <div class="alert-banner">
                    <div class="alert-title">
                        {a["alert_priority"]} — {a["primary_risk"]}
                    </div>
                    <div class="alert-copy">
                        Current MAP <strong>{f["map_current"]:.1f}</strong> mmHg ·
                        Forecast +15 min <strong>{a["predicted_map_15min"]:.1f}</strong> mmHg ·
                        Trajectory <strong>{f["trajectory"]}</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="good-banner">
                    Current risk state: <strong>{level}</strong> ·
                    trajectory: <strong>{f["trajectory"]}</strong>
                </div>
                """,
                unsafe_allow_html=True,
            )

        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            metric_card(
                "Current MAP",
                f"{f['map_current']:.1f}",
                "mmHg",
            )

        with c2:
            metric_card(
                "MAP +10 min",
                f"{f['predicted_map_10min']:.1f}",
                "forecast",
            )

        with c3:
            metric_card(
                "MAP +15 min",
                f"{f['predicted_map_15min']:.1f}",
                "forecast",
            )
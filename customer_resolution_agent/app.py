import html
import logging
import os
import sys
import traceback
from datetime import datetime

import streamlit as st

from data import CUSTOMERS, POLICY, EXERCISE_DATE
from agent import resolve, welcome

# ----------------------------------------------------------------------------
# Deployment-level configuration
# ----------------------------------------------------------------------------
APP_VERSION = "1.0.0"
MAX_MESSAGE_CHARS = 2000          # reject/trim absurdly long input
MAX_HISTORY_TURNS = 200           # cap in-memory session growth per user

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s [resolution-agent] %(message)s",
    stream=sys.stdout,  # stdout logging is what most hosts (Cloud Run, ECS, etc.) capture
)
logger = logging.getLogger("resolution_agent")

st.set_page_config(page_title="AIONOS Resolution Agent", page_icon="✈️", layout="wide")

# ----------------------------------------------------------------------------
# Palette — light lavender, pink→cream, cream, and blue pastels
# ----------------------------------------------------------------------------
BG_LAVENDER = "#C7B4EE"
CARD_FOCUS_GRADIENT = "linear-gradient(135deg, #F6BFC9 0%, #F7E9C9 100%)"
PINK = "#F2A6BB"
PINK_SOFT = "#FBDEE6"
CREAM = "#F5E9C6"
CREAM_SOFT = "#FBF3DE"
BLUE = "#A9D5F2"
BLUE_SOFT = "#DCEEFB"
WHITE = "#FFFFFF"
TEXT_DARK = "#3B2C55"
TEXT_MUTED = "#6B5B87"

TIER_ICONS = {"Gold": "🥇", "Silver": "🥈", "Platinum": "💎"}
USER_AVATAR = "🧑‍💼"
AGENT_AVATAR = "✈️"

STATUS_META = {
    "initiated":    ("✅", "#2E7D63", "#DCF4EA"),
    "eligible":     ("✅", "#2E7D63", "#DCF4EA"),
    "arranged":     ("✅", "#2E7D63", "#DCF4EA"),
    "payable":      ("💳", "#2662A6", "#DCEEFB"),
    "requested":    ("📨", "#2662A6", "#DCEEFB"),
    "pending_choice": ("🕓", "#8A6D1F", "#FBF0D2"),
    "pending":      ("🕓", "#8A6D1F", "#FBF0D2"),
    "information_required": ("❓", "#8A6D1F", "#FBF0D2"),
    "not_eligible": ("🚫", "#B14A63", "#FBDEE6"),
    "not_authorized": ("🚫", "#B14A63", "#FBDEE6"),
    "blocked":      ("⛔", "#B14A63", "#FBDEE6"),
    "escalated":    ("⚠️", "#B14A63", "#FBDEE6"),
    "required":     ("❓", "#8A6D1F", "#FBF0D2"),
    "created":      ("⚠️", "#B14A63", "#FBDEE6"),
}

st.markdown("""
<style>
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes popIn {
    0%   { opacity: 0; transform: scale(0.92); }
    70%  { opacity: 1; transform: scale(1.02); }
    100% { opacity: 1; transform: scale(1); }
}
@keyframes softPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.55; }
}

html, body, .stApp { scroll-behavior: smooth; }
.stApp { background: #C7B4EE; }

section[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #E4D9F7;
}
section[data-testid="stSidebar"] * { color: #3B2C55; }

#MainMenu, footer {visibility: hidden;}
.block-container { padding-top: 1.4rem; max-width: 1100px; }

h1, h2, h3 { color: #3B2C55 !important; font-weight: 800 !important; }
p, span, label, .stMarkdown { color: #3B2C55 !important; }
[data-testid="stCaptionContainer"] { color: #6B5B87 !important; }

/* Force readable text everywhere Streamlit's own theme (incl. dark mode)
   would otherwise pick a color that disappears against these pastel backgrounds. */
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] span,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMetricLabel"] p,
[data-testid="stMetricValue"] div,
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] div,
[data-testid="stExpander"] p,
[data-testid="stExpander"] span,
[data-testid="stAlertContentInfo"] p,
[data-testid="stAlertContentInfo"] span,
.stCodeBlock, .stCodeBlock code, .stCodeBlock span {
    color: #3B2C55 !important;
}

/* Title row */
.title-row { display: flex; align-items: center; gap: 10px; animation: fadeInUp 0.4s ease; }
.title-row .plane-icon { font-size: 1.7rem; display: inline-block; animation: fly 3.2s ease-in-out infinite; }
@keyframes fly {
    0%, 100% { transform: translateX(0) rotate(0deg); }
    50% { transform: translateX(4px) rotate(6deg); }
}

/* Metrics */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #F6BFC9 0%, #F7E9C9 100%);
    border-radius: 16px;
    padding: 14px 16px;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    animation: fadeInUp 0.35s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 18px rgba(59, 44, 85, 0.18);
}
[data-testid="stMetricLabel"] { color: #6B5B87 !important; }
[data-testid="stMetricValue"] { color: #3B2C55 !important; font-weight: 800 !important; }

/* Buttons */
.stButton > button {
    background: #FFFFFF;
    color: #3B2C55;
    border: 1.5px solid #E4D9F7;
    border-radius: 999px;
    font-weight: 700;
    padding: 6px 18px;
    transition: all 0.16s ease;
}
.stButton > button:hover {
    background: #FBDEE6;
    border-color: #F2A6BB;
    color: #3B2C55;
    transform: translateY(-1px) scale(1.02);
    box-shadow: 0 6px 14px rgba(242, 166, 187, 0.45);
}
.stButton > button:active { transform: translateY(0) scale(0.98); }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] {
    background: #FFFFFF;
    border-radius: 999px;
    color: #6B5B87;
    padding: 6px 16px;
    font-weight: 700;
    transition: all 0.16s ease;
}
.stTabs [data-baseweb="tab"]:hover {
    background: #FBDEE6;
    transform: translateY(-1px);
}
.stTabs [aria-selected="true"] {
    background: #F2A6BB !important;
    color: #3B2C55 !important;
    box-shadow: 0 4px 10px rgba(242, 166, 187, 0.5);
}

/* Selectbox */
[data-testid="stSelectbox"] > div > div {
    border-radius: 12px !important;
    transition: box-shadow 0.16s ease;
}
[data-testid="stSelectbox"] > div > div:hover {
    box-shadow: 0 0 0 3px rgba(242, 166, 187, 0.35);
}

/* Expander */
[data-testid="stExpander"] {
    background: #FBF3DE;
    border: 1px solid #F0E4BE;
    border-radius: 14px;
    transition: box-shadow 0.16s ease;
}
[data-testid="stExpander"]:hover { box-shadow: 0 4px 14px rgba(59, 44, 85, 0.08); }
[data-testid="stExpander"] summary { color: #3B2C55; font-weight: 700; }

/* Chat bubbles */
[data-testid="stChatMessage"] {
    border-radius: 16px;
    padding: 6px 10px;
    animation: popIn 0.3s cubic-bezier(0.22, 1, 0.36, 1);
    transition: box-shadow 0.16s ease;
}
[data-testid="stChatMessage"]:hover { box-shadow: 0 4px 14px rgba(59, 44, 85, 0.10); }
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: #FBDEE6;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: #DCEEFB;
}

/* Chat input */
[data-testid="stChatInput"] textarea { border-radius: 14px !important; }

/* Code block (example prompt) */
.stCodeBlock, pre { border-radius: 14px !important; }

/* Divider */
hr { border-color: #E4D9F7 !important; }

.info-card {
    border-radius: 16px; padding: 14px 18px; font-size: 0.9rem;
    color: #3B2C55; margin-bottom: 10px;
    animation: fadeInUp 0.35s ease;
}

/* Status badge */
.status-badge {
    display: inline-flex; align-items: center; gap: 4px;
    border-radius: 999px; padding: 2px 10px 2px 8px;
    font-size: 0.78rem; font-weight: 700;
    animation: popIn 0.28s ease;
}

/* Action / log entry cards */
.log-card {
    border-radius: 14px; padding: 10px 14px; margin-bottom: 8px;
    background: #FFFFFF; border: 1px solid #E4D9F7;
    animation: fadeInUp 0.3s ease;
    transition: box-shadow 0.16s ease, transform 0.16s ease;
}
.log-card:hover { box-shadow: 0 6px 16px rgba(59, 44, 85, 0.10); transform: translateX(2px); }
.log-time { color: #8A7BA8; font-size: 0.76rem; font-weight: 600; }
.log-role { color: #3B2C55; font-weight: 800; }
.log-detail { color: #6B5B87; font-size: 0.88rem; margin-top: 2px; }

/* Waiting indicator */
.waiting-pill {
    display: inline-flex; align-items: center; gap: 6px;
    animation: softPulse 1.6s ease-in-out infinite;
}

/* Sidebar section headers */
.side-head { display: flex; align-items: center; gap: 6px; font-weight: 800; }
</style>
""", unsafe_allow_html=True)


def reset(customer):
    """Start a fresh conversation: the assistant opens with a professional greeting
    that already reflects this customer's booking, and that greeting is audited too."""
    st.session_state.active_customer = customer
    st.session_state.pending_context = {}
    greeting = welcome(customer)
    st.session_state.messages = [{"role": "assistant", "content": greeting}]
    st.session_state.action_log = []
    log("Agent", greeting)


def log(role, detail):
    st.session_state.action_log.append({"time": datetime.now().strftime("%H:%M:%S"), "role": role, "detail": detail})


def init():
    if "messages" not in st.session_state:
        reset(list(CUSTOMERS)[0])


init()

st.markdown(
    '<div class="title-row"><span class="plane-icon">✈️</span>'
    '<h1 style="margin:0;">Customer-Facing Resolution Agent</h1></div>',
    unsafe_allow_html=True,
)
st.caption(f"🗓️ Airline disruption prototype • Exercise date: {EXERCISE_DATE} • 📘 Policy-grounded demo")

with st.sidebar:
    st.markdown('<div class="side-head">🎫 Demo customer</div>', unsafe_allow_html=True)
    names = list(CUSTOMERS)
    tier_labels = {n: f"{TIER_ICONS.get(CUSTOMERS[n]['tier'], '⭐')} {n}" for n in names}
    selected = st.selectbox(
        "Select customer", names, index=names.index(st.session_state.active_customer),
        format_func=lambda n: tier_labels[n],
    )
    if selected != st.session_state.active_customer:
        reset(selected)
        st.rerun()
    c = CUSTOMERS[selected]
    st.metric(f"{TIER_ICONS.get(c['tier'], '⭐')} Loyalty tier", c["tier"])
    st.write(f"🎟️ **PNR:** {c['pnr']}")
    st.write(f"📞 **Contact:** {c['contact']}")
    st.write(f"🧳 **Travel history:** {c['history']}")
    if st.button("🔄 Reset conversation", use_container_width=True):
        reset(selected)
        st.rerun()
    st.divider()
    st.markdown('<div class="side-head">🛡️ Guardrails</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-card" style="background:#F5E9C6;">🚧 Uses only supplied exercise data. '
        'It does not invent seat availability, prices, refund destinations, or extra compensation.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("📜 Policy reference"):
        for v in POLICY.values():
            st.write("•", v)

conversation, actions, booking = st.tabs(["💬 Conversation", "📋 Action record", "🧾 Booking & policy"])
with conversation:
    if len(st.session_state.messages) <= 1:
        st.info("💡 Try the assignment scenario, an edge case such as a legal threat or alternate refund method, "
                "or ask about your booking (e.g. \"What are my booking details?\").")
        examples = {
            "Priya Nair": "I'm furious. I want a full cash refund plus a free business-class upgrade on my return.",
            "Arvind Kulkarni": "This delay is frustrating. I want a hotel because I'm missing my meeting.",
            "Meher Kaur": "I want a full-night hotel and a different higher-fare flight. The fare difference is ₹2,000.",
        }
        st.code(examples[selected], language=None)
    for msg in st.session_state.messages:
        avatar = USER_AVATAR if msg["role"] == "user" else AGENT_AVATAR
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(msg["content"])
    prompt = st.chat_input("Type the customer's message")
    if prompt is not None and prompt.strip():
        prompt = prompt.strip()
        if len(prompt) > MAX_MESSAGE_CHARS:
            st.warning(f"That message is a bit long — please keep it under {MAX_MESSAGE_CHARS} characters.")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            log("Customer", prompt)
            try:
                with st.spinner("✈️ Checking policy and booking details…"):
                    result = resolve(selected, prompt, context=st.session_state.pending_context)
            except Exception:
                # Never let an unhandled exception crash a customer-facing session or
                # leak a stack trace to the browser. Log the full trace server-side
                # and hand the conversation to a human instead.
                logger.error(
                    "resolve() failed for customer=%r prompt=%r\n%s",
                    selected, prompt, traceback.format_exc(),
                )
                fallback = ("I'm sorry — I hit a technical issue processing that. "
                            "I've flagged this conversation for a colleague to pick up.")
                st.session_state.messages.append({"role": "assistant", "content": fallback})
                log("Agent", fallback)
                log("Escalation", "technical_issue")
            else:
                st.session_state.pending_context = result.next_context
                st.session_state.messages.append({"role": "assistant", "content": result.message})
                log("Agent", result.message)
                for a in result.actions:
                    log("Action", f"{a.action_type} — {a.status}: {a.detail}")
                if result.escalation:
                    log("Escalation", result.escalation)

            # Cap unbounded per-session memory growth (long-lived browser tabs).
            st.session_state.messages = st.session_state.messages[-MAX_HISTORY_TURNS:]
            st.session_state.action_log = st.session_state.action_log[-MAX_HISTORY_TURNS * 3:]
            st.rerun()

    if st.session_state.pending_context.get("awaiting_fare_difference"):
        st.markdown(
            '<span class="waiting-pill">🕓 Waiting on the customer for the fare-difference amount '
            'before this rebooking can proceed.</span>',
            unsafe_allow_html=True,
        )

def status_badge(status):
    icon, fg, bg = STATUS_META.get(status, ("ℹ️", "#3B2C55", "#DCEEFB"))
    return (f'<span class="status-badge" style="background:{bg};color:{fg};">'
            f'{icon} {html.escape(status)}</span>')

ROLE_ICONS = {"Customer": "🧑‍💼", "Agent": "✈️"}

with actions:
    st.subheader("📋 Auditable conversation & action trail")
    st.caption("Every customer message, agent decision, action, and escalation — in order, with timestamps.")
    if not st.session_state.action_log:
        st.info("No actions recorded yet.")
    for item in st.session_state.action_log:
        # item["detail"] can originate from raw customer input (the "Customer"
        # role) and is rendered via unsafe_allow_html below, so it must be
        # HTML-escaped — never trust it as markup.
        safe_time = html.escape(item["time"])
        if item["role"] == "Action":
            atype, rest = item["detail"].split(" — ", 1)
            status, detail = rest.split(": ", 1)
            st.markdown(
                f'<div class="log-card">'
                f'<span class="log-time">{safe_time}</span> &nbsp; '
                f'<span class="log-role">⚙️ Action — {html.escape(atype)}</span> &nbsp; {status_badge(status)}'
                f'<div class="log-detail">{html.escape(detail)}</div></div>',
                unsafe_allow_html=True,
            )
        elif item["role"] == "Escalation":
            st.markdown(
                f'<div class="log-card">'
                f'<span class="log-time">{safe_time}</span> &nbsp; '
                f'<span class="log-role">🚨 Escalation</span> &nbsp; {status_badge("escalated")}'
                f'<div class="log-detail">routed to: {html.escape(item["detail"])}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            icon = ROLE_ICONS.get(item["role"], "💬")
            st.markdown(
                f'<div class="log-card">'
                f'<span class="log-time">{safe_time}</span> &nbsp; '
                f'<span class="log-role">{icon} {html.escape(item["role"])}</span>'
                f'<div class="log-detail">{html.escape(item["detail"])}</div></div>',
                unsafe_allow_html=True,
            )

with booking:
    st.subheader("🧾 Customer booking")
    st.write({"customer": selected, "tier": c["tier"], "pnr": c["pnr"]})
    STATUS_ICON = {"cancelled": "❌", "delayed": "⏱️", "unaffected": "✅"}
    for no, f in c["flights"].items():
        icon = STATUS_ICON.get(f["status"], "✈️")
        with st.expander(f"{icon} {no} · {f['route']} · {f['status_display']}", expanded=True):
            st.json(f)
    st.subheader("📘 Decision policy")
    for k, v in POLICY.items():
        st.write(f"**{k.replace('_', ' ').title()}:** {v}")
st.divider()
st.caption("ℹ️ Actions are simulated/recorded locally because the assignment provides no live airline booking, payment, CRM, inventory, voucher, lounge, or hotel API.")
st.caption(f"v{APP_VERSION}")
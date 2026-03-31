import streamlit as st
from streamlit.components.v1 import html

def _inject_base_styles():
    st.markdown(
        """
        <style>
        /* Minimal white hero with green accents */
        .landing-hero-bg {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 36px 32px;
            color: #0f172a;
        }
        .landing-hero-bg:before { display:none; }
        .landing-title {
            font-size: 46px; line-height: 1.05; font-weight: 800; margin: 0 0 8px 0;
            letter-spacing: -0.02em;
            background: #22c55e; /* green background */
            color: #ffffff;      /* white text */
            display: inline-block;
            padding: 8px 14px;
            border-radius: 12px;
        }
        .landing-subtitle { color: #065f46; font-size: 18px; margin-bottom: 18px; }
        .pill { display:inline-flex; gap:8px; align-items:center; padding:6px 12px; border-radius:9999px; background:#0e1117; color:#ecfdf5; font-size:13px; }
        .cta-wrap { display:flex; gap:12px; flex-wrap:wrap; margin-top:10px }
        .cta-primary { background:#22c55e; color:#062d17; padding:10px 16px; border-radius:10px; font-weight:700; border:0; cursor:pointer; }
        .cta-primary:hover { background:#16a34a; }
        .cta-secondary { background:transparent; color:#22c55e; padding:10px 16px; border-radius:10px; font-weight:700; border:1px solid rgba(34,197,94,.35); cursor:pointer; }
        .feature-card { background:#0e1117; border:1px solid rgba(34,197,94,.22); border-radius:12px; padding:16px; height:100%; }
        .feature-title { color:#064e3b; font-weight:700; margin:6px 0; }
        .feature-desc { color:#065f46; font-size:14px; }
        .muted { color:#9ca3af; }
        .center { text-align:center; }
        .footnote { color:#9ca3af; font-size:12px; }
        .compact { margin-top: -8px; }
        /* Force green hero button regardless of theme */
        .landing-hero-bg .stButton > button {
            background: #22c55e !important;
            color: #062d17 !important;
            border: 0 !important;
            border-radius: 10px !important;
        }
        .landing-hero-bg .stButton > button:hover {
            background: #16a34a !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _lottie(url: str, height: int = 320):
    """Embed a Lottie animation via CDN. Falls back on nothing if blocked."""
    # Uses the official LottieFiles player
    player = f"""
    <script src="https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js"></script>
    <lottie-player src="{url}"
        background="transparent" speed="1" style="width:100%;height:{height}px" loop autoplay>
    </lottie-player>
    """
    html(player, height=height + 16)


def render_landing():
    """Attractive landing page with animations and a CTA.

    Authentication is handled exclusively via the sidebar; no inline auth here.
    """
    _inject_base_styles()

    # Load banner
    #banner_path = Path("app/static/banner.png")
    #if banner_path.exists():
    #    st.image(str(banner_path), use_container_width=True)

    # Hero section (minimalist)
    with st.container():
        st.markdown('<div class="landing-hero-bg">', unsafe_allow_html=True)
        st.markdown(
            "<div class='landing-subtitle compact'>Import statements, track your portfolio, and forecast outcomes — all in one place.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Features grid (clean, consistent)
    f1, f2, f3 = st.columns(3, gap="large")
    with f1:
        st.markdown("<div class='feature-card'><div class='feature-title'>Performance</div><div class='feature-desc'>Track day gain, XIRR, CAGR, and volatility.</div></div>", unsafe_allow_html=True)
    with f2:
        st.markdown("<div class='feature-card'><div class='feature-title'>Imports</div><div class='feature-desc'>Upload statements; parsing and categorization automated.</div></div>", unsafe_allow_html=True)
    with f3:
        st.markdown("<div class='feature-card'><div class='feature-title'>Forecasts</div><div class='feature-desc'>Model outcomes with Monte Carlo simulations.</div></div>", unsafe_allow_html=True)

    st.markdown("\n")
    st.caption("Built with Streamlit • Secure • Fast • Friendly")

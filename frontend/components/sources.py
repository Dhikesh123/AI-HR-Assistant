"""Source citation rendering."""
from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st


def render_sources(sources: List[Dict[str, Any]], key: str = "") -> None:
    """Render the citation block shown under an answer."""
    if not sources:
        return

    label = f"Sources ({len(sources)})"
    with st.expander(label, expanded=True):
        for source in sources:
            document = source.get("document", "unknown")
            page = source.get("page")
            section = source.get("section")
            score = source.get("score")

            line = f"**{document}**"
            if page is not None:
                line += f" &nbsp;·&nbsp; Page {page}"
            if section and section.lower() != "general":
                line += f" &nbsp;·&nbsp; {section}"
            st.markdown(line, unsafe_allow_html=True)
            if score is not None:
                st.progress(min(max(float(score), 0.0), 1.0), text=f"relevance {score:.2f}")

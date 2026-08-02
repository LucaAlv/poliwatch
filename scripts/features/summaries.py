from typing import Any

import render_dip_pulse_html as html

from . import BaseComponent, REGISTRY


class SummariesComponent(BaseComponent):
    def enrich_report(self, report: dict[str, Any], ctx: dict[str, Any]) -> None:
        callback = ctx.get("reuse_existing_llm_summaries")
        if callback and ctx.get("summary_mode") == "reuse":
            callback(report, ctx.get("existing_report"))

    def dossier_sections(self, report: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
        if ctx.get("scope") == "session":
            return [
                html.render_session_llm_summary(
                    ctx["items"],
                    ctx["stats_by_index"],
                    ctx.get("summary_generation"),
                    ctx["protocol"],
                )
            ]
        return [
            html.render_llm_summary(
                ctx["item"],
                ctx["stats"],
                ctx.get("summary_generation"),
                ctx["protocol"],
            )
        ]


COMPONENT = SummariesComponent(REGISTRY["summaries"])

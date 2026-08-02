from typing import Any

import render_dip_pulse_html as html

from . import BaseComponent, REGISTRY


class DevViewComponent(BaseComponent):
    def dossier_sections(self, report: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
        callback = ctx.get("render_dev_sections")
        if callback:
            return list(callback(report, ctx) or [])
        if ctx.get("scope") == "protocol":
            return [html.render_protocol_api_overview(report)]
        return [html.render_top_dev_details(ctx["item"])]


COMPONENT = DevViewComponent(REGISTRY["dev-view"])

from typing import Any

from . import BaseComponent, REGISTRY


class AwProfilesComponent(BaseComponent):
    def enrich_report(self, report: dict[str, Any], ctx: dict[str, Any]) -> None:
        callback = ctx.get("enrich_report_with_profiles")
        if callback:
            callback(report, ctx.get("profile_resolver"))


COMPONENT = AwProfilesComponent(REGISTRY["aw-profiles"])

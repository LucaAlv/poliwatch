from pathlib import Path
from typing import Any

from . import BaseComponent, REGISTRY


class AbgeordneteComponent(BaseComponent):
    def after_persist(self, conn: Any, ctx: dict[str, Any]) -> None:
        collect = ctx.get("collect_abgeordnete")
        if collect:
            ctx["abg_mps"], ctx["mp_lookup"] = collect(conn)

    def write_pages(self, output_dir: Path, ctx: dict[str, Any]) -> dict[str, Any]:
        return ctx["write_abgeordnete_pages"](
            output_dir,
            ctx.get("abg_mps") or [],
            ctx["selection"],
            ctx.get("publication_domains"),
        )


COMPONENT = AbgeordneteComponent(REGISTRY["mp-pages"])

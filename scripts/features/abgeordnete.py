from pathlib import Path
from typing import Any

from . import BaseComponent, REGISTRY


class AbgeordneteComponent(BaseComponent):
    def after_persist(self, conn: Any, ctx: dict[str, Any]) -> None:
        ingest = ctx.get("ingest_mdb_roster")
        if ingest and "mp-roster" in ctx["selection"]:
            ctx["roster_stats"] = ingest(
                ctx["client"],
                conn,
                wahlperiode=ctx["roster_wahlperiode"],
                profile_resolver=ctx.get("profile_resolver"),
            )
        collect = ctx.get("collect_abgeordnete")
        if collect:
            ctx["abg_mps"], ctx["mp_lookup"] = collect(conn)

    def write_pages(self, output_dir: Path, ctx: dict[str, Any]) -> dict[str, Any]:
        return ctx["write_abgeordnete_pages"](
            output_dir,
            ctx.get("abg_mps") or [],
            ctx["selection"],
        )


COMPONENT = AbgeordneteComponent(REGISTRY["mp-pages"])

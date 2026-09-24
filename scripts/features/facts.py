from pathlib import Path
from typing import Any

from . import BaseComponent, REGISTRY


class FactsComponent(BaseComponent):
    def write_pages(self, output_dir: Path, ctx: dict[str, Any]) -> dict[str, Any]:
        return ctx["write_facts_pages"](
            output_dir,
            ctx["database_path"],
            ctx["no_persist"],
            ctx.get("mp_lookup"),
            ctx.get("document_numbers") or set(),
            ctx.get("bill_slugs") or set(),
            ctx["selection"],
        )


COMPONENT = FactsComponent(REGISTRY["facts"])

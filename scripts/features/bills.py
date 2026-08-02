from pathlib import Path
from typing import Any

from . import BaseComponent, REGISTRY


class BillsComponent(BaseComponent):
    def write_pages(self, output_dir: Path, ctx: dict[str, Any]) -> dict[str, Any]:
        bills = ctx["collect_bill_pages"](ctx["entries"])
        return ctx["write_bill_pages"](
            output_dir,
            bills,
            ctx.get("mp_lookup"),
            ctx["selection"],
        )


COMPONENT = BillsComponent(REGISTRY["bills"])

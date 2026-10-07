from .models import Warehouse


def stock_report(wh: Warehouse) -> str:
    lines = [f"Warehouse: {wh.name}"]
    for sku in sorted(wh.items):
        it = wh.items[sku]
        lines.append(f"{sku}  {it.name:<20} {it.qty:>5}")
    return "\n".join(lines)

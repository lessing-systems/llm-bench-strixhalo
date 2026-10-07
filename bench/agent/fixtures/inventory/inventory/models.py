from dataclasses import dataclass, field


@dataclass
class Item:
    sku: str
    name: str
    unit_price: float
    qty: int = 0


@dataclass
class Warehouse:
    name: str
    items: dict = field(default_factory=dict)

    def add(self, item: Item):
        if item.sku in self.items:
            self.items[item.sku].qty += item.qty
        else:
            self.items[item.sku] = item

    def remove(self, sku: str, qty: int):
        it = self.items[sku]
        it.qty -= qty
        if it.qty == 0:
            del self.items[sku]

    def total_value(self):
        return sum(i.unit_price * i.qty for i in self.items.values())

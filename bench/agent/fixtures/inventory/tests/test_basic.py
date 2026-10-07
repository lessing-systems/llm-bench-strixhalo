from inventory import Item, Warehouse


def test_add_and_value():
    w = Warehouse("main")
    w.add(Item("A1", "bolt", 0.5, 10))
    w.add(Item("A1", "bolt", 0.5, 5))
    assert w.items["A1"].qty == 15
    assert w.total_value() == 7.5

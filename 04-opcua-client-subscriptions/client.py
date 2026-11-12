"""
OPC UA client: browse, read with metadata, subscribe, write, call methods.

The point of this example is the difference between polling and a
subscription: with a subscription the SERVER samples the value and only
sends a notification when it changes (by more than the deadband), so the
network carries changes, not repeated reads.

Run example 03 first, then:
    python 04-opcua-client-subscriptions/client.py
"""
import asyncio
import os

from asyncua import Client, ua

URL = os.getenv("OPCUA_URL", "opc.tcp://localhost:4841/iiot-examples/")
NS_URI = "urn:iiot-protocols-examples:plant"


async def browse(node, depth=0, max_depth=4, out=None):
    """Recursive browse, like the tree in UaExpert."""
    out = [] if out is None else out
    name = (await node.read_browse_name()).Name
    cls = await node.read_node_class()
    out.append(("  " * depth) + f"{name}  [{cls.name}]")
    if depth < max_depth and cls in (ua.NodeClass.Object, ua.NodeClass.ObjectType) or depth == 0:
        for child in await node.get_children(refs=ua.ObjectIds.HierarchicalReferences):
            if (await child.read_node_class()) in (ua.NodeClass.Object, ua.NodeClass.Variable, ua.NodeClass.Method):
                await browse(child, depth + 1, max_depth, out)
    return out


class Counter:
    """Subscription handler: called by the library on every data change."""

    def __init__(self, verbose=True, names=None):
        self.names = names or {}
        self.n = 0
        self.last = {}
        self.verbose = verbose

    def datachange_notification(self, node, val, data):
        self.n += 1
        ts = data.monitored_item.Value.SourceTimestamp
        name = self.names.get(node.nodeid, str(node.nodeid.Identifier))
        self.last[name] = val
        if self.verbose:
            shown = f"{val:.1f}" if isinstance(val, float) else repr(val)
            print(f"  {ts:%H:%M:%S.%f}"[:15] + f"  {name:<12} = {shown}")


async def run(seconds: float = 8, url: str = URL, verbose: bool = True) -> dict:
    p = print if verbose else (lambda *a, **k: None)
    async with Client(url) as c:
        idx = await c.get_namespace_index(NS_URI)
        filler = await c.nodes.objects.get_child([f"{idx}:Plant", f"{idx}:Line1", f"{idx}:Filler01"])

        p("== browse ==")
        for line in await browse(filler):
            p("  " + line)

        speed = await filler.get_child(f"{idx}:Speed")
        units = await (await speed.get_child("0:EngineeringUnits")).read_value()
        rng = await (await speed.get_child("0:EURange")).read_value()
        p(f"\n== metadata == Speed in {units.DisplayName.Text}, range {rng.Low}..{rng.High}")

        p("\n== method calls ==")
        p("  Start() ->", await filler.call_method(f"{idx}:Start"))

        target = await filler.get_child([f"{idx}:Setpoints", f"{idx}:TargetSpeed"])
        await target.write_value(ua.Variant(300.0, ua.VariantType.Double))
        p("  wrote TargetSpeed = 300")
        try:
            await speed.write_value(ua.Variant(1.0, ua.VariantType.Double))
        except ua.UaStatusCodeError as e:
            p("  write to Speed refused by server:", type(e).__name__)

        p(f"\n== subscription for {seconds:.0f} s (publishing interval 500 ms) ==")
        names = ["State", "Speed", "GoodCount", "RejectCount"]
        nodes = [await filler.get_child(f"{idx}:{n}") for n in names]
        handler = Counter(verbose, {n.nodeid: name for n, name in zip(nodes, names)})
        sub = await c.create_subscription(500, handler)
        # Plain monitored items for the discrete values...
        await sub.subscribe_data_change([nodes[0], nodes[2], nodes[3]], sampling_interval=250)
        # ...and an absolute deadband on Speed: notify only if it moves more than 5 bottles/min
        await sub.deadband_monitor(nodes[1], 5.0, deadbandtype=1)
        await asyncio.sleep(seconds)
        await sub.delete()

        polls = int(seconds / 0.25) * len(nodes)
        p(f"\n  {handler.n} notifications received; polling the same 4 tags every 250 ms "
          f"would have been {polls} reads.")
        p("  Stop() ->", await filler.call_method(f"{idx}:Stop"))
        return {"notifications": handler.n, "polls": polls, "state": await nodes[0].read_value()}


if __name__ == "__main__":
    asyncio.run(run())

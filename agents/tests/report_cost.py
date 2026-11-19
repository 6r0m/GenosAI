"""What the skill system costs an agent, as one diffable table.

Not a test: there is no correct number, only a trend. Run it before and after a change
to the shared contracts and diff the two outputs. Tokens are chars/4 - consistent
between runs, which is what a trend needs; not exact.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skilltree as ST

AI = os.path.abspath(os.path.join(ST.AGENTS, os.pardir))
ALWAYS = ["engineering-change-principles.md", "review-contract.md"]
CONDITIONAL = ["documentation-structure.md", "content-rules.md"]


def cost(path):
    text = ST.read(path)
    return len(text) // 4, len(text.splitlines())


def main():
    rows = []
    print("SKILL SYSTEM CONTEXT COST      (approx tokens = chars/4)")
    print("=" * 64)

    # AGENTS.md is the largest always-loaded item and was missing here, which made the
    # worst case read smaller than the floor every session already pays.
    agents_md = ST.read(os.path.join(ST.AGENTS, "AGENTS.md"))
    always = len(agents_md) // 4
    listing = 0
    for name, _, fm, _ in ST.skills():
        listing += len(fm.get("description", "")) // 4
    print("\nL0  loaded in EVERY session")
    print(f"      {'AGENTS.md':<32}{always:>8} tok  {len(agents_md.splitlines()):>4} lines")
    print(f"      {'skill listing':<32}{listing:>8} tok")
    print(f"      {'subtotal':<32}{always + listing:>8} tok")
    listing += always

    print("\nL1  SKILL.md body, on invoke")
    for name, path, _, body in ST.skills():
        t = len(body) // 4
        rows.append((name, t))
        print(f"      {name:<32}{t:>8} tok  {len(body.splitlines()):>4} lines")

    print("\nL2  shared contracts, on applicable work or change/review skill invoke")
    always = 0
    for f in ALWAYS:
        t, n = cost(os.path.join(ST.SHARED, f))
        always += t
        print(f"      {f:<32}{t:>8} tok  {n:>4} lines")
    print(f"      {'subtotal':<32}{always:>8} tok")

    print("\nL3  conditional")
    cond = 0
    for f in CONDITIONAL:
        t, n = cost(os.path.join(ST.SHARED, f))
        cond += t
        print(f"      {f:<32}{t:>8} tok  {n:>4} lines")
    t, n = cost(os.path.join(ST.SKILLS, "architect", "references", "component-driven.md"))
    cond += t
    print(f"      {'component-driven.md':<32}{t:>8} tok  {n:>4} lines")
    names = sorted(os.listdir(ST.TEMPLATES))
    tpl = sum(cost(os.path.join(ST.TEMPLATES, f))[0] for f in names)
    print(f"      {f'templates ({len(names)}, if all read)':<32}{tpl:>8} tok")

    arch = dict(rows)["architect"]
    worst = listing + arch + always + cond + max(
        cost(os.path.join(ST.TEMPLATES, f))[0] for f in os.listdir(ST.TEMPLATES))
    print("\n" + "-" * 64)
    print(f"WORST CASE  architect + every conditional read{'':2}{worst:>8} tok")
    print("            before the agent opens one repository file")

    # Routing reach: the metric that says whether traversal actually works.
    print("\n" + "=" * 64)
    print("ROUTING REACH   (router nodes reachable from their parent's README)")
    for label, root in [("project", AI)]:
        nodes = ST.router_nodes(root)
        routed = ST.routes(nodes)
        top = os.path.normpath(root)
        reach = sum(1 for n in nodes if n == top or n in routed)
        print(f"      {label:<14}{reach:>4} / {len(nodes):<4} router nodes reachable")



if __name__ == "__main__":
    main()

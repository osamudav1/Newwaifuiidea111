import ast
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load_rarity_logic(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {"RARITY_EMOJI", "VALID_RARITIES", "MAX_RARITY_LENGTH", "_normal_rarity"}
    nodes = [node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef)) and any(
        (isinstance(target, ast.Name) and target.id in wanted)
        for target in getattr(node, "targets", [])
    ) or (isinstance(node, ast.FunctionDef) and node.name == "_normal_rarity")]
    namespace = {"re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


for filename in (
    "YUKIWAFUS/modules/ADMIN/addwaifu.py",
    "YUKIWAFUS/modules/ADMIN/edit.py",
):
    ns = load_rarity_logic(ROOT / filename)
    normalize = ns["_normal_rarity"]
    assert normalize("Common") == "Common"
    assert normalize("Special Edition") == "Special Edition"
    assert normalize("1-star") == "1-star"
    assert normalize("  limited   edition ") == "Limited Edition"
    assert normalize("Seasonal Collector 2026") == "Seasonal Collector 2026"
    assert normalize("") is None
    assert normalize("x" * (ns["MAX_RARITY_LENGTH"] + 1)) is None

print("rarity wizard logic: OK")

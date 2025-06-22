import ast
import os

ALLOWED_BUILTINS = {"list", "dict", "set", "tuple"}


def test_no_pep585_generics():
    viols = []
    for root, _, files in os.walk(os.path.dirname(os.path.dirname(__file__))):
        for file in files:
            if file.endswith(".py") and not file.startswith("test_"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    source = f.read()
                try:
                    tree = ast.parse(source)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Subscript) and isinstance(
                        node.value, ast.Name
                    ):
                        if node.value.id in ALLOWED_BUILTINS:
                            viols.append(f"{path}:{node.lineno}")
    assert not viols, "PEP585 generics found: " + ", ".join(viols)

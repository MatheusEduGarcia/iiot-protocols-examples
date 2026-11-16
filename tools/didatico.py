"""
Camada didática para os notebooks de estudo.

Insere células markdown (marcadas com a tag "didatico") em notebooks já executados,
sem tocar nas células de código nem nas saídas:

  * "Antes de começar" logo após o título
  * "Pare e preveja" antes de experimentos-chave
  * "Erros comuns", "Teste seu entendimento", "Exercícios", "Glossário" e "Próximo passo" no final

Idempotente: rodar de novo remove as células antigas com a tag e reinsere.
Uso: python tools/didatico.py tools/didatico_conteudo.py .
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

TAG = "didatico"


def md(text: str) -> dict:
    cid = "did-" + hashlib.sha1(text.encode()).hexdigest()[:12]
    return {"cell_type": "markdown", "id": cid, "metadata": {"tags": [TAG]}, "source": text.strip("\n").splitlines(keepends=True)}


def intro(d: dict) -> str:
    goals = "\n".join(f"- {g}" for g in d["goals"])
    out = f"""### Antes de começar

| | |
|---|---|
| **Para quem** | {d["who"]} |
| **Pré-requisitos** | {d["prereq"]} |
| **Tempo** | {d["time"]} |

**Ao final você consegue:**

{goals}

**Onde isso aparece na fábrica:** {d["factory"]}

**Uma analogia para guardar:** {d["analogy"]}

> **Como estudar:** rode uma célula por vez. Sempre que aparecer **Pare e preveja**, responda mentalmente antes de executar. Errar a previsão é o que faz o conceito fixar."""
    return out


def predict(text: str) -> str:
    return f"> **Pare e preveja.** {text}"


def ending(d: dict) -> str:
    parts = ["---", "## Erros comuns", ""]
    parts += [f"- **{e}** {fix}" for e, fix in d["mistakes"]]
    parts += ["", "## Teste seu entendimento", "", "Responda antes de abrir cada resposta.", ""]
    for i, (q, a) in enumerate(d["quiz"], 1):
        parts += [f"**{i}. {q}**", "", "<details><summary>Ver resposta</summary>", "", a, "", "</details>", ""]
    parts += ["## Exercícios para praticar", ""]
    parts += [f"{i}. {e}" for i, e in enumerate(d["exercises"], 1)]
    parts += ["", "## Glossário", "", "| Termo | Significado |", "|---|---|"]
    parts += [f"| **{t}** | {m} |" for t, m in d["glossary"]]
    if d.get("next"):
        parts += ["", f"**Próximo passo:** {d['next']}"]
    return "\n".join(parts)


def apply(path: Path, d: dict):
    nb = json.loads(path.read_text(encoding="utf-8"))
    cells = [c for c in nb["cells"] if TAG not in c.get("metadata", {}).get("tags", [])]
    preds = d.get("predict", {})
    out = []
    for i, c in enumerate(cells):
        if i in preds:
            assert c["cell_type"] == "code", f"{path.name}: predict index {i} is not a code cell"
            out.append(md(predict(preds[i])))
        out.append(c)
        if i == 0:
            out.append(md(intro(d)))
    out.append(md(ending(d)))
    nb["cells"] = out
    path.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return len(out) - len(cells)


if __name__ == "__main__":
    spec = importlib.util.spec_from_file_location("content", sys.argv[1])
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    root = Path(sys.argv[2])
    for rel, d in mod.NOTEBOOKS.items():
        print(f"{rel}: +{apply(root / rel, d)} células didáticas")

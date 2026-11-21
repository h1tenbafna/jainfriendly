"""Text normalisation shared by the lexicon and the analyser.

Label text and lexicon phrases go through the *same* normalisation, so lexicon authors only
write one spelling of each phrase.
"""

from __future__ import annotations

import re
import unicodedata

# British/American and common label spelling variants -> one canonical token.
SPELLING = {
    "flavor": "flavour",
    "flavoring": "flavouring",
    "flavored": "flavoured",
    "color": "colour",
    "colored": "coloured",
    "colouring": "colour",
    "coloring": "colour",
    "fiber": "fibre",
    "sulfite": "sulphite",
    "sulfur": "sulphur",
    "sulfate": "sulphate",
    "bisulfite": "bisulphite",
    "metabisulfite": "metabisulphite",
    "iodized": "iodised",
    "lodised": "iodised",  # OCR: capital I read as l
    "lodized": "iodised",
    "iodine": "iodine",
    "stabilizer": "stabiliser",
    "stabilizing": "stabilising",
    "hydrolyzed": "hydrolysed",
    "autolyzed": "autolysed",
    "emulsifying": "emulsifying",
    "yoghurt": "yogurt",
    "gelatine": "gelatin",
    "chili": "chilli",
    "chilly": "chilli",  # "chillies" after plural stemming
    "leave": "leaf",  # "leaves" after plural stemming
    "soyabean": "soybean",
    "chile": "chilli",
    "mayonaise": "mayonnaise",
    "favour": "flavour",  # common typo on labels
    "caramelised": "caramelized",
    "fortified": "fortified",
    "aluminum": "aluminium",
}

# Words that describe form/processing and don't change *what* an ingredient is.
DESCRIPTORS = frozenset(
    """
    powder dehydrated dried dry extract flake paste refined edible natural organic roasted fried
    ground whole crushed chopped minced granule granulated piece solid and of with from the in a
    an fresh frozen pure premium mixed blend toasted salted sweetened unsweetened concentrate
    juice puree pulp added permitted contain contains ingredient raw cooked split skinned peeled
    sliced diced bit cube chip chunk roast coated pre gelatinised enriched fortified iodised
    double filtered cold pressed hydrogenated partially fully non as or for to by used also may
    less than at quality grade select fine coarse kashmiri byadgi guntur desi indian soluble
    insoluble stuff product mix food type style made using containing approx approximately
    percent per cent pc pcs min max quantity qty roasted dressed seasoned spiced
    ins e no number shudh satva swad
    """.split()
)


def _stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("oes"):
        return token[:-2]
    if (
        len(token) > 3
        and token.endswith("s")
        and not token.endswith(("ss", "us", "is"))
    ):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Lower-case, strip accents, split into canonical tokens."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", " and ").replace("'", "").replace("’", "")
    tokens = re.findall(r"[a-z0-9]+", text)
    out = []
    for t in tokens:
        t = SPELLING.get(t, t)
        t = _stem(t)
        t = SPELLING.get(t, t)
        out.append(t)
    return out

"""Chinese display names.
data/zh_names.json : {key: 中文名} curated/LLM translations keyed by zh_key(name)
data/zh_glossary.json : {english phrase: 中文} used to translate new names that are not in the dictionary yet
                        (longest phrase first; untranslated words stay in English)."""
import json, re, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = ROOT / 'data' / 'zh_names.json'
GLOSS = ROOT / 'data' / 'zh_glossary.json'


def zh_key(name):
    n = ''.join(c for c in unicodedata.normalize('NFKD', name or '') if not unicodedata.combining(c))
    n = re.sub(r'\b(19|20)\d\d\b', ' ', n)
    n = re.sub(r'\b\d+(\.\d+)?\s*(ml|cl|l)\b', ' ', n, flags=re.I)
    n = re.sub(r'\bNV\b', ' ', n)
    n = re.sub(r'\(.*?\)', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip(' ,-')
    return n.lower()


_names = json.load(open(NAMES, encoding='utf-8')) if NAMES.exists() else {}
_gloss = json.load(open(GLOSS, encoding='utf-8')) if GLOSS.exists() else {}
_gloss_items = sorted(_gloss.items(), key=lambda kv: -len(kv[0]))
_gloss_re = [(re.compile(r'(?<![a-z])' + re.escape(k.lower()) + r'(?![a-z])'), v) for k, v in _gloss_items]


def fallback(name):
    """Rule-based partial translation: known phrases -> Chinese, everything else kept."""
    k = zh_key(name)
    if not k:
        return ''
    out = k
    hits = 0
    for rx, v in _gloss_re:
        out, n = rx.subn('\u0000' + v + '\u0000', out)
        hits += n
    if not hits:
        return ''
    out = out.replace('\u0000', ' ')
    out = re.sub(r'\s*,\s*', ' ', out)
    out = re.sub(r'\s+', ' ', out).strip()
    # tidy: capitalise leftover latin words
    out = ' '.join(w if not re.match(r'^[a-z]', w) else w[0].upper() + w[1:] for w in out.split())
    # remove spaces between adjacent Chinese chunks
    out = re.sub(r'(?<=[一-鿿])\s+(?=[一-鿿])', '', out)
    return out


def zh_name(name):
    """(chinese, from_dictionary)"""
    k = zh_key(name)
    v = _names.get(k)
    if v:
        return v, True
    return fallback(name), False

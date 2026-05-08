"""
search_engine/tokenizer.py
──────────────────────────
Identical tokenization pipeline to crawler/tokenizer.py.
NO NLTK download required. Must produce identical output so index tokens
and query tokens always match.
"""

import re
import os

_USE_STEMMING = os.environ.get("USE_STEMMING", "1").strip() != "0"

_STOP_WORDS: set = {
    "a","about","above","after","again","against","all","am","an","and",
    "any","are","as","at","be","because","been","before","being","below",
    "between","both","but","by","can","could","did","do","does","doing",
    "don","down","during","each","few","for","from","further","get","got",
    "had","has","have","having","he","her","here","hers","him","himself",
    "his","how","if","in","into","is","it","its","itself","just","let",
    "me","more","most","my","myself","no","nor","not","now","of","off",
    "on","once","only","or","other","our","ours","out","over","own","re",
    "same","she","should","so","some","such","than","that","the","their",
    "theirs","them","then","there","these","they","this","those","through",
    "to","too","under","until","up","us","very","was","we","were","what",
    "when","where","which","while","who","whom","why","will","with","would",
    "you","your","yours","yourself","http","https","www","com","org",
    "html","htm","php","asp","was","been","has","had","also","may","one",
    "two","use","used","new","way","back","see","like","well","even",
    "make","take","made","come","came","said","first","last","long","little",
    "own","right","old","next","high","large","different","small","large",
    "early","young","important","public","private","real","best","free",
    "many","great","still","just","same","another","than","then","here",
    "there","ever","never","often","always","already","now","however",
    "though","since","while","both","either","neither","nor","not","only",
    "other","than","then","too","very","can","could","may","might","shall",
    "should","will","would","must","need","dare","ought","used",
}


class _PorterStemmer:
    _VOWEL = re.compile(r"[aeiou]")
    _STEP1A = [("sses","ss"),("ies","i"),("ss","ss"),("s","")]
    _STEP1B = [("eed","ee"),("ed",""),("ing","")]
    _STEP2 = [
        ("ational","ate"),("tional","tion"),("enci","ence"),("anci","ance"),
        ("izer","ize"),("bli","ble"),("alli","al"),("entli","ent"),
        ("eli","e"),("ousli","ous"),("ization","ize"),("ation","ate"),
        ("ator","ate"),("alism","al"),("iveness","ive"),("fulness","ful"),
        ("ousness","ous"),("aliti","al"),("iviti","ive"),("biliti","ble"),
    ]
    def stem(self, w: str) -> str:
        if len(w) <= 2:
            return w
        for suf, rep in self._STEP1A:
            if w.endswith(suf):
                w = w[: len(w)-len(suf)] + rep
                break
        for suf, rep in self._STEP1B:
            if w.endswith(suf):
                base = w[: len(w)-len(suf)] + rep
                if self._VOWEL.search(base):
                    w = base
                break
        for suf, rep in self._STEP2:
            if w.endswith(suf) and len(w) > len(suf)+1:
                w = w[: len(w)-len(suf)] + rep
                break
        if w.endswith("e") and len(w) > 4:
            w = w[:-1]
        return w


_stemmer = _PorterStemmer()


class Tokenizer:

    def __init__(self, use_stemming: bool = _USE_STEMMING):
        self._use_stemming = use_stemming

    def tokenize(self, text: str) -> list:
        text   = text.lower()
        tokens = re.findall(r"\b[a-z][a-z0-9]*\b", text)
        tokens = [t for t in tokens if t not in _STOP_WORDS and len(t) > 2]
        if self._use_stemming:
            tokens = [_stemmer.stem(t) for t in tokens]
        return tokens

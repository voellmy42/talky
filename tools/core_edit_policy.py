"""Conservative bilingual fact checks for rewrites, not a proof of equivalent meaning."""
import re

_DAYS = {
    'monday': 'mon', 'montag': 'mon', 'tuesday': 'tue', 'dienstag': 'tue',
    'wednesday': 'wed', 'mittwoch': 'wed', 'thursday': 'thu', 'donnerstag': 'thu',
    'friday': 'fri', 'freitag': 'fri', 'saturday': 'sat', 'samstag': 'sat',
    'sunday': 'sun', 'sonntag': 'sun',
}
_CONDITIONS = {'before': 'before', 'vor': 'before', 'after': 'after', 'nach': 'after',
               'until': 'until', 'bis': 'until'}


def clean_edit_output(text, source, instruction):
    """Drop accidental whole-answer quotes, preserving quoted input/quote requests."""
    text = text.strip()
    pairs = [('"', '"'), ('“', '”'), ('„', '“'), ("'", "'")]
    if (any(source.lstrip().startswith(left) for left, _ in pairs)
            or re.search(r'\b(?:quote|quotes|quotation|Anführungszeichen|zitiere)\b', instruction, re.I)):
        return text
    for left, right in pairs:
        if len(text) > 2 and text.startswith(left) and text.endswith(right):
            return text[len(left):-len(right)].strip()
    return text


def preserves_edit_details(source, candidate):
    """Keep written numbers, named weekdays, negation and explicit time conditions.

    Intentional factual changes are outside this first editing milestone. These
    checks can reject valid rewrites, especially translations into other languages.
    Roles, scope, tone and all other semantic relationships still need review.
    """
    def details(text):
        words = re.findall(r"\w+(?:['’]\w+)*", text.casefold())
        numbers = {re.sub(r'\s+', '', value) for value in re.findall(
            r'(?<!\w)[+-]?(?:\d+(?:[.,]\d+)*|[.,]\d+)(?:\s*%)?', text)}
        days = {_DAYS[word] for word in words if word in _DAYS}
        conditions = {_CONDITIONS[word] for word in words if word in _CONDITIONS}
        if re.search(r'\bby\s+(?:next\s+)?(?:' + '|'.join(_DAYS) + r'|\d)', text.casefold()):
            conditions.add('until')
        negative = any(word in ('not', 'no', 'never', 'without', 'cannot', 'nothing', 'nobody',
                               'nicht', 'nie', 'niemals', 'nichts', 'niemand', 'ohne')
                       or word.endswith(("n't", 'n’t'))
                       or re.fullmatch(r'kein(?:e|en|em|er|es)?', word) for word in words)
        return numbers, days, conditions, negative
    original, edited = details(source), details(candidate)
    return (original[0] == edited[0] and original[1] == edited[1]
            and original[2] == edited[2] and original[3] == edited[3])

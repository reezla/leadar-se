from __future__ import annotations

import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from lead_finder.providers.google_search_parse import hostname

GENERIC_LOCAL_PARTS = {"info", "kontakt", "contact", "hello", "hej", "sales", "order"}
_FIRST = {"fornamn", "firstname", "fornamnet"}
_DOT = {"fornamn.efternamn", "firstname.lastname", "fornamn.lastname", "firstname.efternamn"}
_HYPHEN = {"fornamn-efternamn", "firstname-lastname", "fornamn-lastname"}
_JUNK_LOCALS = {
    "noreply", "no-reply", "donotreply", "do-not-reply", "webmaster", "postmaster",
    "admin", "privacy", "gdpr", "wordpress", "example", "test", "user", "name",
    "email", "yourname", "mail", "abuse",
}
_JUNK_DOMAINS = {"example.com", "example.se", "sentry.io", "wixpress.com", "schema.org"}
_NOT_A_NAME = {
    "ab", "hb", "kb", "inc", "ltd", "gmbh", "kontakta", "kontakt", "oss", "hem",
    "telefon", "tele", "epost", "e-post", "e.post", "email", "e-mail", "e.mail",
    "mail", "adress", "sverige", "sweden", "intresseanmalan", "projekt",
    "hyresratter", "privat", "sida", "nya", "ny", "butik", "vag", "gata", "box",
    "eller", "och",
}
_ASCII = str.maketrans(
    {"å": "a", "ä": "a", "ö": "o", "é": "e", "ü": "u", "ø": "o", "á": "a", "à": "a", "ë": "e"}
)
_NAME_WORD_RE = re.compile(r"[A-ZÅÄÖÉÜ][a-zåäöéü'\-]{1,40}")
_TOKEN_RE = re.compile(r"[A-Za-zÅÄÖÉÜåäöéü'\-]+|\d+")
_AT = r"(?:@|\s*(?:\[|\(|\{)\s*(?:at|a)\s*(?:\]|\)|\})\s*|\s+snabela\s+)"
_EMAIL_RE = re.compile(
    rf"([A-Za-z0-9._%+\-åäöÅÄÖéÉüÜ]+){_AT}([A-Za-z0-9.\-]+\.[A-Za-z]{{2,}})",
    re.IGNORECASE,
)
_NAME_WINDOW = 400


def suggested_email(html: str, *, page_url: str | None = None) -> str | None:
    host = hostname(page_url) if page_url else ""
    generic: str | None = None
    resolved: str | None = None
    published: str | None = None
    text = _visible_text(html)
    for match in _EMAIL_RE.finditer(text):
        kind, address = _classify(match.group(1), match.group(2), host, text[: match.start()])
        if kind == "generic":
            generic = generic or address
        elif kind == "resolved":
            resolved = resolved or address
        elif kind == "published":
            published = published or address
    return generic or resolved or published


def _visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    for tag in soup.select('a[href^="mailto:"]'):
        address = unquote(str(tag.get("href", "")).split(":", 1)[-1]).split("?", 1)[0].strip()
        if address:
            tag.append(f" {address}")
    return " ".join(soup.get_text(" ", strip=True).split())


def _classify(local: str, domain: str, host: str, prefix: str) -> tuple[str, str]:
    domain = domain.casefold().strip(".")
    folded = _ascii_local(local)
    if _junk_domain(domain) or not folded:
        return "skip", ""
    if folded in GENERIC_LOCAL_PARTS:
        return "generic", f"{folded}@{domain}"
    if not _same_site(domain, host):
        return "skip", ""
    placeholder = _placeholder(folded)
    if placeholder:
        person = _person_for(prefix, domain)
        if person is None:
            return "skip", ""
        return "resolved", _mailbox(person, placeholder, domain)
    if folded in _JUNK_LOCALS or folded.startswith(("noreply", "no-reply")):
        return "skip", ""
    return "published", f"{folded}@{domain}"


def _placeholder(local: str) -> str | None:
    if local in _FIRST:
        return "first"
    if local in _DOT:
        return "dot"
    if local in _HYPHEN:
        return "hyphen"
    return None


def _mailbox(person: tuple[str, str], kind: str, domain: str) -> str:
    first = _ascii_local(person[0])
    last = _ascii_local(person[1])
    if kind == "dot":
        local = f"{first}.{last}"
    elif kind == "hyphen":
        local = f"{first}-{last}"
    else:
        local = first
    return f"{local}@{domain}"


def _person_for(prefix: str, domain: str) -> tuple[str, str] | None:
    tokens = _TOKEN_RE.findall(prefix[-_NAME_WINDOW:])
    people: list[tuple[str, str]] = []
    for index, token in enumerate(tokens):
        if token.isdigit() or (index > 0 and tokens[index - 1].isdigit()):
            continue
        for length in (2, 3):
            chunk = tokens[index : index + length]
            if len(chunk) != length or not all(_NAME_WORD_RE.fullmatch(part) for part in chunk):
                break
            person = _split_name(" ".join(chunk))
            if person is not None:
                people.append(person)
    for person in reversed(people):
        if not _name_is_company(person, domain):
            return person
    return None


def _split_name(value: str) -> tuple[str, str] | None:
    parts = value.split()
    if any(_fold(part) in _NOT_A_NAME for part in parts):
        return None
    return parts[0], parts[-1]


def _name_is_company(person: tuple[str, str], domain: str) -> bool:
    stem = _fold(domain.split(".", 1)[0])
    first = _fold(person[0])
    last = _fold(person[1])
    if len(first) < 4:
        return False
    return stem.startswith(first) or (first in stem and last in stem)


def _same_site(domain: str, host: str) -> bool:
    if not host:
        return True
    domain = domain.removeprefix("www.")
    return domain == host or host.endswith(f".{domain}") or domain.endswith(f".{host}")


def _junk_domain(domain: str) -> bool:
    domain = domain.removeprefix("www.")
    return domain in _JUNK_DOMAINS or domain.endswith((".example", ".invalid", ".test"))


def _ascii_local(value: str) -> str:
    return re.sub(r"[^a-z0-9._+-]", "", _fold(value))


def _fold(value: str) -> str:
    return value.casefold().replace("æ", "ae").translate(_ASCII)

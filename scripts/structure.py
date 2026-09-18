"""문단 리스트를 EPUB용 Markdown으로 구조화한다.

HWP·HWPX·TXT는 제목 계층 정보를 신뢰할 수 없으므로 텍스트 패턴으로 장·절을
복원한다. 원고 안에 목차가 있으면 그 목차를 작품 제목 사전으로 삼는다.
"""
import re

# 장 제목 패턴
CHAPTER_PATTERNS = [
    re.compile(r"^\s*제?\s*\d+\s*장[.\s·]"),
    re.compile(r"^\s*\d+\s*장\s*$"),
    re.compile(r"^\s*(?:Chapter|CHAPTER)\s+\d+"),
    re.compile(r"^\s*제?\s*\d+\s*부[.\s·]"),
]
# 이름이 정해진 앞·뒤 글
NAMED_SECTIONS = {
    "여는 글", "닫는 글", "머리말", "서문", "prologue", "프롤로그",
    "에필로그", "맺는 글", "나가는 글", "들어가며", "나가며", "추천사", "감사의 글",
}
TOC_MARKERS = {"목차", "차례", "contents", "table of contents"}
GENRE_PREFIX = re.compile(r"^[-·•*]?\s*(시|수필|소설|산문|희곡|동화)\s*[:：]\s*(.*)$")

# 마크다운 특수문자 이스케이프
_ESCAPE = re.compile(r"([\\`*_\[\]<>|])")
_LEADING = re.compile(r"^(\s*)([#>+])")
_LEADING_NUM = re.compile(r"^(\s*)(\d+)([.)])\s")


def normalize(text):
    """제목 비교용 정규화: 공백·괄호·한자·문장부호 제거"""
    text = re.sub(r"[(（\[].*?[)）\]]", "", text)          # 괄호와 그 내용
    text = re.sub(r"[一-鿿㐀-䶿]", "", text)  # 한자
    text = re.sub(r"[\s.,·:;!?'\"“”‘’~\-—]", "", text)     # 공백·문장부호
    return text.lower()


def escape_md(text):
    text = _ESCAPE.sub(r"\\\1", text)
    text = _LEADING.sub(r"\1\\\2", text)
    text = _LEADING_NUM.sub(r"\1\2\\\3 ", text)
    return text


def is_chapter(text):
    return any(p.match(text) for p in CHAPTER_PATTERNS) or normalize(text) in {
        normalize(s) for s in NAMED_SECTIONS
    }


def parse_toc(paragraphs):
    """목차 블록에서 작품 제목 사전과 블록 범위를 얻는다.

    반환: (works, start, end) — works는 {정규화제목: 'verse'|'prose'}
    목차가 없으면 (빈 dict, None, None)
    """
    start = None
    for i, text in enumerate(paragraphs):
        if text and normalize(text) in {normalize(m) for m in TOC_MARKERS}:
            start = i
            break
    if start is None:
        return {}, None, None

    works = {}
    chapters_seen = []
    genre = None
    end = len(paragraphs)
    for i in range(start + 1, len(paragraphs)):
        text = paragraphs[i]
        if not text:
            continue
        # 목차에 나왔던 장 제목이 다시 나오면 본문 시작으로 본다
        if normalize(text) in chapters_seen:
            end = i
            break
        if is_chapter(text):
            chapters_seen.append(normalize(text))
            genre = None
            continue
        match = GENRE_PREFIX.match(text)
        if match:
            genre = "verse" if match.group(1) in ("시",) else "prose"
            body = match.group(2)
        else:
            body = text
        if genre is None:
            continue
        for item in re.split(r"[,、.·]", body):
            item = item.strip()
            if item:
                works[normalize(item)] = genre
    return works, start, end


def to_markdown(paragraphs, drop_leading=0):
    """문단 리스트 → Markdown 본문"""
    works, toc_start, toc_end = parse_toc(paragraphs)

    lines = []
    genre = "prose"      # 현재 절의 장르
    verse_buffer = []
    body_started = False

    def flush_verse():
        if verse_buffer:
            lines.extend("| " + escape_md(v) for v in verse_buffer)
            lines.append("")
            verse_buffer.clear()

    for i, text in enumerate(paragraphs):
        if i < drop_leading:
            continue
        if toc_start is not None and toc_start <= i < toc_end:
            continue  # 목차 블록은 EPUB 내비게이션이 대신한다
        if not text:
            flush_verse()
            continue

        if is_chapter(text):
            flush_verse()
            lines.append(f"\n# {escape_md(text)}\n")
            genre = "prose"
            body_started = True
            continue

        key = normalize(text)
        if key in works:
            flush_verse()
            lines.append(f"\n## {escape_md(text)}\n")
            genre = works[key]
            body_started = True
            continue

        if not body_started:
            # 본문 앞 서지 정보는 행 단위로 보존한다
            lines.append("| " + escape_md(text))
            continue

        # 운문 판정: 시 절은 전부 행으로, 산문 절은 짧고 문장이 끊기지 않은 행만
        is_verse = genre == "verse" or (
            len(text) <= 25 and not re.search(r"[.!?]\s", text)
        )
        if is_verse:
            verse_buffer.append(text)
        else:
            flush_verse()
            lines.append(escape_md(text))
            lines.append("")

    flush_verse()
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"

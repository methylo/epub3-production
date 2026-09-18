"""HWP 5.x(.hwp) 본문 추출 모듈.

한글 5.0 바이너리 포맷은 OLE 복합문서 안에 zlib(raw deflate)로 압축된
레코드 스트림으로 저장된다. 이 모듈은 본문 문단 텍스트만 추출한다.
표·이미지·글상자는 EPUB 리플로우 대상이 아니므로 추출하지 않는다.

의존성: olefile
"""
import struct
import zlib

try:
    import olefile
except ImportError:  # pragma: no cover
    raise SystemExit("olefile이 필요합니다. `pip install olefile`로 설치하세요.")

HWPTAG_BEGIN = 0x010
PARA_HEADER = HWPTAG_BEGIN + 50   # 66
PARA_TEXT = HWPTAG_BEGIN + 51     # 67

# HWP 5.0 스펙의 제어문자 분류
INLINE = {4, 5, 6, 7, 8, 9, 19, 20}
EXTENDED = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}


def records(buf):
    """레코드 스트림을 (tag, level, payload)로 순회한다."""
    i, n = 0, len(buf)
    while i + 4 <= n:
        header = struct.unpack_from("<I", buf, i)[0]
        i += 4
        tag = header & 0x3FF
        level = (header >> 10) & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            size = struct.unpack_from("<I", buf, i)[0]
            i += 4
        yield tag, level, buf[i:i + size]
        i += size


def decode_text(payload):
    """PARA_TEXT payload(UTF-16LE + 제어문자)를 문자열로 바꾼다."""
    out = []
    i, n = 0, len(payload)
    while i + 2 <= n:
        code = struct.unpack_from("<H", payload, i)[0]
        if code in INLINE or code in EXTENDED:
            i += 16  # 확장 제어문자는 8 wchar(16바이트)를 차지한다
            continue
        if code < 32:
            if code in (10, 13):
                out.append("\n")
            elif code in (24, 30, 31):
                out.append(" ")
            i += 2
            continue
        out.append(chr(code))
        i += 2
    return "".join(out)


def _stream(ole, name, compressed):
    data = ole.openstream(name).read()
    return zlib.decompress(data, -15) if compressed else data


def extract_paragraphs(path):
    """HWP 파일에서 문단 텍스트 리스트를 반환한다."""
    ole = olefile.OleFileIO(str(path))
    try:
        header = ole.openstream("FileHeader").read()
        if header[:17] != b"HWP Document File":
            raise SystemExit(f"HWP 5.x 파일이 아닙니다: {path}")
        flags = struct.unpack("<I", header[36:40])[0]
        if flags & 0x02:
            raise SystemExit("암호가 설정된 문서입니다. 한글에서 암호를 해제한 뒤 다시 실행하세요.")
        if flags & 0x04:
            raise SystemExit("배포용 문서입니다. 배포용 잠금을 해제한 뒤 다시 실행하세요.")
        compressed = bool(flags & 0x01)

        names = ["/".join(entry) for entry in ole.listdir()]
        sections = sorted(n for n in names if n.startswith("BodyText/Section"))
        if not sections:
            raise SystemExit("본문(BodyText) 스트림이 없습니다.")

        paragraphs = []
        for section in sections:
            body = _stream(ole, section, compressed)
            current = None
            for tag, _level, payload in records(body):
                if tag == PARA_HEADER:
                    current = []
                    paragraphs.append(current)
                elif tag == PARA_TEXT and current is not None:
                    current.append(decode_text(payload))
        return [" ".join("".join(p).split()) for p in paragraphs]
    finally:
        ole.close()


def extract_cover(path, out_path):
    """미리보기 이미지(PrvImage)를 표지 후보로 저장한다. 없으면 None."""
    ole = olefile.OleFileIO(str(path))
    try:
        if not ole.exists("PrvImage"):
            return None
        data = ole.openstream("PrvImage").read()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        with open(out_path, "wb") as fh:
            fh.write(data)
        return out_path
    finally:
        ole.close()

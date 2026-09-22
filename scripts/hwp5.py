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
BIN_DATA = HWPTAG_BEGIN + 2       # 18  (DocInfo)
PARA_HEADER = HWPTAG_BEGIN + 50   # 66
PARA_TEXT = HWPTAG_BEGIN + 51     # 67
SHAPE_PICTURE = HWPTAG_BEGIN + 69 # 85  (그림 개체)

# HWPTAG_SHAPE_COMPONENT_PICTURE 안에서 BinItem ID가 놓인 위치.
# 테두리(12) + 사각형 꼭지점(32) + 자르기(16) + 안쪽 여백(8) = 68,
# 이어서 밝기·명암·효과 각 1바이트를 지나면 71이다.
PICTURE_BINITEM_OFFSET = 71

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


def _bin_extensions(doc):
    """DocInfo의 HWPTAG_BIN_DATA에서 {BinItem ID: 확장자}를 얻는다.

    레코드는 등장 순서대로 1번부터 번호가 매겨진다.
    payload: 속성(2) + 스토리지 ID(2) + 확장자 길이(2) + 확장자(UTF-16LE)
    """
    exts = {}
    for index, (tag, _level, payload) in enumerate(
            ((t, l, p) for t, l, p in records(doc) if t == BIN_DATA), start=1):
        if len(payload) < 6:
            continue
        storage_id = struct.unpack_from("<H", payload, 2)[0]
        length = struct.unpack_from("<H", payload, 4)[0]
        ext = payload[6:6 + length * 2].decode("utf-16-le", "replace")
        exts[index] = (storage_id, ext.lower())
    return exts


def extract_document(path):
    """문단 텍스트와 그림 배치를 함께 반환한다.

    반환: (paragraphs, images)
      paragraphs — 문단 텍스트 리스트
      images     — [(문단 index, 확장자, 바이트)] 본문 등장 순서
    """
    ole = olefile.OleFileIO(str(path))
    try:
        compressed = _check_header(ole, path)
        exts = _bin_extensions(_stream(ole, "DocInfo", compressed))
        names = ["/".join(entry) for entry in ole.listdir()]

        paragraphs, images = [], []
        for section in sorted(n for n in names if n.startswith("BodyText/Section")):
            body = _stream(ole, section, compressed)
            current = None
            for tag, _level, payload in records(body):
                if tag == PARA_HEADER:
                    current = []
                    paragraphs.append(current)
                elif tag == PARA_TEXT and current is not None:
                    current.append(decode_text(payload))
                elif tag == SHAPE_PICTURE and len(payload) >= PICTURE_BINITEM_OFFSET + 2:
                    bin_id = struct.unpack_from("<H", payload, PICTURE_BINITEM_OFFSET)[0]
                    if bin_id not in exts:
                        continue
                    storage_id, ext = exts[bin_id]
                    data = _read_bindata(ole, names, storage_id, ext)
                    if data:
                        images.append((len(paragraphs) - 1, ext, data))

        texts = [" ".join("".join(p).split()) for p in paragraphs]
        return texts, images
    finally:
        ole.close()


def _read_bindata(ole, names, storage_id, ext):
    """BinData/BIN####.ext 스트림을 읽는다. 대소문자 표기가 섞여 있어 맞춰 찾는다."""
    prefix = f"BinData/BIN{storage_id:04X}."
    for name in names:
        if name.upper().startswith(prefix.upper()):
            data = ole.openstream(name).read()
            # 압축 저장된 경우(속성 하위 비트)가 있어 zlib 실패는 원본으로 둔다
            if data[:2] not in (b"\x89P", b"\xff\xd8", b"GI", b"BM", b"II", b"MM"):
                try:
                    return zlib.decompress(data, -15)
                except zlib.error:
                    pass
            return data
    return None


def _check_header(ole, path):
    header = ole.openstream("FileHeader").read()
    if header[:17] != b"HWP Document File":
        raise SystemExit(f"HWP 5.x 파일이 아닙니다: {path}")
    flags = struct.unpack("<I", header[36:40])[0]
    if flags & 0x02:
        raise SystemExit("암호가 설정된 문서입니다. 한글에서 암호를 해제한 뒤 다시 실행하세요.")
    if flags & 0x04:
        raise SystemExit("배포용 문서입니다. 배포용 잠금을 해제한 뒤 다시 실행하세요.")
    return bool(flags & 0x01)


def extract_paragraphs(path):
    """HWP 파일에서 문단 텍스트 리스트를 반환한다."""
    return extract_document(path)[0]


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

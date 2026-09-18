#!/usr/bin/env python3
"""원고를 EPUB 3으로 변환하고 epubcheck로 검증한다.

지원 입력: .md  .docx  .txt  .hwp  .hwpx
사용 예:
    python scripts/build_epub.py manuscript.hwp \
        --title "책 제목" --author "홍순성" --language ko-KR \
        --cover cover.png --output "책제목_v1.0.epub"
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent))

# HWP 입력에 필요한 olefile이 없으면 스킬 전용 venv로 다시 실행한다.
# venv의 python은 베이스 인터프리터와 같은 실행 파일을 가리키므로
# 실행 파일 경로가 아니라 sys.prefix로 현재 venv 안인지 판별한다.
try:
    import olefile  # noqa: F401
except ImportError:
    _venv_dir = Path(__file__).resolve().parent.parent / ".venv"
    for _sub in ("bin/python", "Scripts/python.exe"):
        _py = _venv_dir / _sub
        if _py.is_file() and Path(sys.prefix).resolve() != _venv_dir.resolve():
            os.execv(str(_py), [str(_py), str(Path(__file__).resolve()), *sys.argv[1:]])

import structure  # noqa: E402

SUPPORTED = {".md", ".markdown", ".docx", ".txt", ".hwp", ".hwpx"}
TXT_CHAPTER = re.compile(r"^\s*(제?\s*\d+\s*장|Chapter\s+\d+|CHAPTER\s+\d+)\b")


# ---------------------------------------------------------------- 실행 도구

def find_pandoc():
    path = os.environ.get("PANDOC_BIN") or shutil.which("pandoc")
    if not path:
        sys.exit("pandoc을 찾지 못했습니다. 설치하거나 PANDOC_BIN 환경변수로 경로를 지정하세요.")
    return [path]


def find_epubcheck():
    jar = os.environ.get("EPUBCHECK_JAR")
    if jar:
        java = os.environ.get("JAVA_BIN") or shutil.which("java")
        if not java:
            sys.exit("EPUBCHECK_JAR을 쓰려면 Java가 필요합니다. JAVA_BIN을 지정하세요.")
        return [java, "-jar", jar]
    path = os.environ.get("EPUBCHECK_BIN") or shutil.which("epubcheck")
    if not path:
        sys.exit("epubcheck를 찾지 못했습니다. 설치하거나 EPUBCHECK_BIN 환경변수로 경로를 지정하세요.")
    return [path]


def check_version(cmd, label):
    try:
        out = subprocess.run(cmd + ["--version"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        sys.exit(f"{label} 실행에 실패했습니다: {exc}")
    if out.returncode != 0:
        sys.exit(f"{label} 실행에 실패했습니다:\n{out.stderr or out.stdout}")
    first = (out.stdout or out.stderr).strip().splitlines()[0]
    print(f"  {label}: {first}")


# ---------------------------------------------------------------- 입력 변환

def paragraphs_from_hwp(path):
    import hwp5
    return hwp5.extract_paragraphs(path)


def paragraphs_from_hwpx(path):
    ns = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}
    paragraphs = []
    with zipfile.ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist()
                       if re.match(r"Contents/section\d+\.xml$", n))
        if not names:
            sys.exit(f"HWPX 본문(Contents/sectionN.xml)이 없습니다: {path}")
        for name in names:
            root = ElementTree.fromstring(zf.read(name))
            for para in root.iter(f"{{{ns['hp']}}}p"):
                runs = [t.text or "" for t in para.iter(f"{{{ns['hp']}}}t")]
                paragraphs.append(" ".join("".join(runs).split()))
    return paragraphs


def paragraphs_from_txt(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return [" ".join(line.split()) for line in text.splitlines()]


def markdown_from_txt(paragraphs):
    """TXT는 장 제목 패턴만 승격하고 나머지는 문단으로 둔다."""
    lines = []
    for text in paragraphs:
        if not text:
            lines.append("")
        elif TXT_CHAPTER.match(text):
            lines.append(f"\n# {structure.escape_md(text)}\n")
        else:
            lines.append(structure.escape_md(text))
            lines.append("")
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"


def build_markdown(src, workdir, drop_leading):
    """입력을 Markdown 경로로 정규화한다. docx/md는 pandoc이 직접 읽는다."""
    suffix = src.suffix.lower()
    if suffix in (".md", ".markdown", ".docx"):
        return src, None
    if suffix == ".hwp":
        paragraphs = paragraphs_from_hwp(src)
        body = structure.to_markdown(paragraphs, drop_leading)
    elif suffix == ".hwpx":
        paragraphs = paragraphs_from_hwpx(src)
        body = structure.to_markdown(paragraphs, drop_leading)
    elif suffix == ".txt":
        paragraphs = paragraphs_from_txt(src)
        body = markdown_from_txt(paragraphs)
    else:
        sys.exit(f"지원하지 않는 입력 형식입니다: {suffix}")
    tmp = workdir / "manuscript.md"
    tmp.write_text(body, encoding="utf-8")
    return tmp, len(paragraphs)


# ---------------------------------------------------------------- 메인

def main():
    ap = argparse.ArgumentParser(description="원고를 EPUB 3으로 변환하고 검증한다.")
    ap.add_argument("input", help="원고 파일 (.md .docx .txt .hwp .hwpx)")
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--language", default="ko-KR")
    ap.add_argument("--publisher", default=None)
    ap.add_argument("--cover", default=None, help="세로형 표지 이미지(JPG/PNG)")
    ap.add_argument("--css", default=None, help="기본값: templates/epub.css")
    ap.add_argument("--output", required=True)
    ap.add_argument("--toc-depth", type=int, default=2)
    ap.add_argument("--drop-leading", type=int, default=0,
                    help="본문 앞에서 버릴 문단 수 (표제지 중복 제거용)")
    ap.add_argument("--keep-markdown", default=None,
                    help="중간 Markdown을 이 경로에 남긴다")
    ap.add_argument("--skip-check", action="store_true", help="epubcheck 검증을 건너뛴다")
    args = ap.parse_args()

    src = Path(args.input).expanduser()
    if not src.is_file():
        sys.exit(f"입력 파일이 없습니다: {src}")
    if src.suffix.lower() not in SUPPORTED:
        sys.exit(f"지원하지 않는 확장자입니다: {src.suffix} (지원: {', '.join(sorted(SUPPORTED))})")

    out = Path(args.output).expanduser()
    if out.suffix.lower() != ".epub":
        sys.exit("--output은 .epub 확장자여야 합니다.")

    skill_root = Path(__file__).resolve().parent.parent
    css = Path(args.css) if args.css else skill_root / "templates" / "epub.css"
    if not css.is_file():
        sys.exit(f"CSS를 찾지 못했습니다: {css}")

    print("[1/4] 실행 도구 확인")
    pandoc = find_pandoc()
    check_version(pandoc, "pandoc")
    epubcheck = None
    if not args.skip_check:
        epubcheck = find_epubcheck()
        check_version(epubcheck, "epubcheck")

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)

        print("[2/4] 원고 구조화")
        md, count = build_markdown(src, workdir, args.drop_leading)
        if count is not None:
            print(f"  문단 {count}개 추출 → {md.name}")
        else:
            print(f"  {src.suffix} 원고를 pandoc이 직접 읽습니다")
        if args.keep_markdown and count is not None:
            shutil.copy(md, Path(args.keep_markdown).expanduser())

        print("[3/4] EPUB 3 생성")
        meta = workdir / "metadata.yaml"
        fields = [
            "---",
            f"title: {yaml_quote(args.title)}",
            f"author: {yaml_quote(args.author)}",
            f"lang: {yaml_quote(args.language)}",
        ]
        if args.publisher:
            fields.append(f"publisher: {yaml_quote(args.publisher)}")
        fields.append("---")
        meta.write_text("\n".join(fields) + "\n", encoding="utf-8")

        cmd = pandoc + [
            str(md), "--from",
            "markdown+line_blocks" if md.suffix == ".md" else "docx",
            "--to", "epub3",
            "--metadata-file", str(meta),
            "--css", str(css),
            "--toc", f"--toc-depth={args.toc_depth}",
            "--split-level=1",
            "--output", str(out),
        ]
        if md.suffix != ".md":
            cmd[cmd.index("--from") + 1] = "docx" if src.suffix.lower() == ".docx" else "markdown+line_blocks"
        if args.cover:
            cover = Path(args.cover).expanduser()
            if not cover.is_file():
                sys.exit(f"표지 이미지를 찾지 못했습니다: {cover}")
            cmd.append(f"--epub-cover-image={cover}")
        out.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            sys.exit(f"pandoc 변환에 실패했습니다:\n{result.stderr}")
        if result.stderr.strip():
            print("  pandoc 경고:\n" + indent(result.stderr.strip()))
        print(f"  생성: {out}  ({out.stat().st_size:,} bytes)")

    print("[4/4] epubcheck 검증")
    if args.skip_check:
        print("  건너뜀 (--skip-check). 배포용으로 완료 처리하지 않습니다.")
        return 0
    check = subprocess.run(epubcheck + [str(out)], capture_output=True, text=True)
    report = (check.stdout + check.stderr).strip()
    errors = len(re.findall(r"^ERROR", report, re.M))
    warnings = len(re.findall(r"^WARNING", report, re.M))
    print(indent(report) if report else "  (출력 없음)")
    print(f"\n결과: 오류 {errors}건 / 경고 {warnings}건")
    if errors or check.returncode != 0:
        print("오류가 있으므로 배포용 EPUB으로 완료 처리하지 않습니다.")
        return 1
    if warnings:
        print("경고가 있습니다. 내용을 확인한 뒤 배포 여부를 판단하세요.")
    return 0


def yaml_quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def indent(text, prefix="  "):
    return "\n".join(prefix + line for line in text.splitlines())


if __name__ == "__main__":
    sys.exit(main())

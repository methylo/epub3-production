---
name: epub3-production
description: Use when converting Markdown, Word, HWP, or text into EPUB 3.
version: 0.4.0
author: 홍순성, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [epub3, ebook, markdown, docx, hwp, hwpx, text, pandoc]
    related_skills: [docx]
---

# EPUB 3 제작

Markdown(`.md`), Word(`.docx`), 한글(`.hwp`·`.hwpx`), 텍스트(`.txt`) 원고를 동일한 EPUB 3 규격으로 변환하고 `epubcheck`로 검증한다. 입력 형식마다 원고 구조화 단계는 다르지만, 최종 산출 규격·메타데이터·검증 기준은 하나로 유지한다.

## When to Use

- Markdown, DOCX, HWP, HWPX, TXT 원고를 EPUB 3 전자책으로 만들 때
- 표지·목차·메타데이터·CSS가 포함된 배포용 EPUB이 필요할 때
- 기존 EPUB이 표준 구조를 충족하는지 검증할 때

## Prerequisites

- `terminal`로 `pandoc --version`과 `epubcheck --version`을 확인한다. 명령이 전역 경로에 없으면 `PANDOC_BIN`, `EPUBCHECK_BIN` 환경변수로 실행 파일을 지정한다.
- EPUBCheck가 JAR로만 제공되면 `EPUBCHECK_JAR`와 `JAVA_BIN` 환경변수로 JAR와 Java 실행 파일을 지정한다.
- 둘 중 하나라도 없으면 설치 또는 실행 환경 준비를 사용자에게 확인한다. 변환 성공으로 간주하지 않는다.
- 최종 메타데이터는 제목, 저자, 언어를 반드시 정한다. 기본 언어는 한국어 원고에 `ko-KR`이다.
- HWP 입력은 파이썬 `olefile` 패키지가 필요하다. 스킬 폴더에 `.venv`가 있으면 스크립트가 자동으로 그 인터프리터로 다시 실행한다.
  없으면 `python3 -m venv .venv && .venv/bin/pip install olefile Pillow`로 스킬 폴더에 만든다. HWPX는 추가 설치가 필요 없다.
- 본문 그림 축소에는 `Pillow`를 쓴다. 없으면 원본 크기 그대로 넣는다.
- 표지 이미지는 세로형 JPG 또는 PNG를 사용한다. HWP는 내장 미리보기(PrvImage)를 표지 후보로 쓸 수 있다.

## Input Rules

| 입력 | 구조 기준 | 변환 전 처리 |
| --- | --- | --- |
| Markdown | 메타데이터 제목, `#` 장, `##` 절 | 표지 제목을 본문의 `#`로 반복하지 않고, 제목 계층·이미지 상대 경로·내부 링크를 확인한다. |
| DOCX | 문서 제목은 Title, 장·절은 Heading 1~3 | 수동 글꼴·여백·페이지 나누기·텍스트 상자는 EPUB 구조가 아니므로 최소화한다. |
| HWP | 본문 문단 + 내장 그림 | 표·글상자는 추출하지 않는다. 그림은 본문 위치에 넣고 `▲`로 시작하는 다음 문단을 설명으로 붙인다. 장 제목은 `N장.`·`제 N장`·`Chapter N` 패턴으로, 작품 제목은 원고 안 목차와 대조해 인식한다. 암호·배포용 잠금 문서는 먼저 해제한다. |
| HWPX | `Contents/sectionN.xml`의 문단 | HWP와 같은 규칙을 적용한다. 별도 설치 없이 표준 라이브러리로 읽는다. |
| TXT | 빈 줄=문단, 장 제목 규칙 | `제 N장`, `Chapter N`, `CHAPTER N`을 최상위 장 제목으로 인식한다. 다른 규칙이면 변환 전에 Markdown으로 구조화한다. |

## Procedure

1. 입력 확장자와 제목·저자·언어·표지·출력 경로를 확인한다. 완료 기준은 필요한 값이 모두 확정된 상태다.
2. Markdown은 제목 계층을, DOCX는 Heading 스타일을, HWP·HWPX·TXT는 장 제목 패턴을 검수한다. 완료 기준은 목차로 쓸 장 구조가 확인된 상태다.
3. `terminal`로 `scripts/build_epub.py`를 실행한다. 이 스크립트는 HWP·HWPX·TXT를 임시 Markdown으로 정규화하고 Pandoc으로 EPUB 3을 생성한다. 중간 Markdown은 `--keep-markdown`으로 남겨 검수한다.
4. 스크립트가 실행한 `epubcheck` 결과를 확인한다. 완료 기준은 오류 0건이다.
5. EPUB 리더에서 표지, 목차, 장 이동, 한글 표시, 이미지, 각주를 실제로 확인한다. 완료 기준은 오류 0건 검증과 리더 검수가 모두 완료된 상태다.

## Commands

```bash
python scripts/build_epub.py manuscript.md \
  --title "책 제목" --author "홍순성" --language ko-KR \
  --cover cover.jpg --output "책제목_v1.0.epub"

python scripts/build_epub.py manuscript.docx \
  --title "책 제목" --author "홍순성" --language ko-KR \
  --cover cover.jpg --output "책제목_v1.0.epub"

python scripts/build_epub.py manuscript.txt \
  --title "책 제목" --author "홍순성" --language ko-KR \
  --cover cover.jpg --output "책제목_v1.0.epub"

python scripts/build_epub.py manuscript.hwp \
  --title "책 제목" --author "저자" --publisher "출판사" --language ko-KR \
  --cover cover.png --drop-leading 2 \
  --keep-markdown check.md --output "책제목_v1.0.epub"
```

`--drop-leading`은 표지에 이미 있는 표제지 문단을 본문에서 제외한다. `--skip-check`는 검증을 건너뛰며 배포용 완료로 보지 않는다. 그림은 `--max-image-width`·`--image-quality`·`--no-images`로 조정한다.

## Files

| 경로 | 역할 |
| --- | --- |
| `scripts/build_epub.py` | 변환·검증 진입점 |
| `scripts/hwp5.py` | HWP 5.x 바이너리 본문 추출 |
| `scripts/structure.py` | 문단 → Markdown 구조화(장·절·운문 판정) |
| `templates/epub.css` | 한국어 본문 기본 스타일 |

## Version Policy

- `version`은 스킬 절차의 버전이다. 새 스킬은 `0.1.0`에서 시작한다.
- 변환 규칙·지원 형식·검증 절차 추가는 minor 버전을 올린다. 예: `0.2.0`.
- 오류 수정은 patch 버전을 올린다. 예: `0.1.1`.
- 기존 명령·산출 구조가 호환되지 않게 바뀌면 major 버전을 올린다. 예: `1.0.0`.
- 전자책 원고 판본은 별도로 `book_version`을 사용하며 출력 파일명에 반영한다. 예: `책제목_v1.0.epub`.

## Pitfalls

- DOCX의 인쇄 조판은 EPUB에서 재현 대상이 아니다. EPUB은 화면 크기에 따라 문장이 흐르는 리플로우 형식이다.
- TXT에는 제목 계층이 없으므로 장 제목 규칙을 자동 인식하지 못하면 한 개 장으로 생성된다.
- `epubcheck` 통과는 모든 리더 앱에서의 시각 품질을 보장하지 않는다.
- `epubcheck` 경고·오류가 있으면 배포용 EPUB으로 완료 처리하지 않는다.
- HWP의 표·글상자는 변환되지 않는다. 신청서·보고서처럼 표 중심 문서는 EPUB 대상이 아니다.
- 본문 그림은 기본값으로 가로 1600px·JPEG 85로 줄인다. 원본 해상도가 필요하면 `--max-image-width`를 올린다.
- 운문 판정은 문단 길이와 문장부호로 추정한다. 시와 산문이 섞인 원고는 `--keep-markdown`으로 중간 결과를 확인한다.

## Verification

- `pandoc --version`과 `epubcheck --version`이 실행된다.
- 출력 파일이 `.epub` 확장자로 생성된다.
- `epubcheck`가 오류 0건으로 종료한다.
- 패키지 메타데이터와 본문 XHTML의 언어 태그가 입력한 언어값과 일치한다.
- EPUB 리더에서 표지·목차·본문·이미지·한글을 확인한다.

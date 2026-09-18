# epub3-production

원고를 **EPUB 3**으로 변환하고 `epubcheck`로 검증하는 도구입니다.
Markdown · Word · 한글(HWP/HWPX) · 텍스트 5종 입력을 하나의 EPUB 규격으로 맞춥니다.

한글 `.hwp`는 바이너리 포맷이라 pandoc이 읽지 못합니다. 이 도구는 HWP 본문을 직접 추출해
장·절 구조를 복원한 뒤 EPUB으로 넘깁니다.

## 할 수 있는 것

- `.md` `.docx` `.txt` `.hwp` `.hwpx` → EPUB 3
- 표지·목차·메타데이터·CSS 포함한 배포용 EPUB 생성
- `epubcheck` 자동 검증 (오류가 있으면 실패로 처리)
- 원고 안 목차를 사전으로 삼아 장·절 제목 인식
- 시(詩)의 행·연 구조 보존

## 설치

### 1단계 — 외부 도구

**이 도구는 pandoc과 epubcheck 없이 동작하지 않습니다.** 파이썬 패키지가 아니므로
`pip`으로 따라오지 않습니다. 먼저 설치하세요.

**macOS**

```bash
brew install pandoc epubcheck
```

**Windows**

```powershell
winget install --id JohnMacFarlane.Pandoc
winget install --id EclipseAdoptium.Temurin.21.JDK
```

epubcheck는 [releases 페이지](https://github.com/w3c/epubcheck/releases)에서 zip을 받아
압축을 풀고 환경변수로 위치를 지정합니다.

```powershell
setx EPUBCHECK_JAR "C:\tools\epubcheck\epubcheck.jar"
```

**Linux**

```bash
sudo apt install pandoc default-jre
# epubcheck는 위 releases 페이지에서 받아 EPUBCHECK_JAR로 지정
```

설치 확인:

```bash
pandoc --version
epubcheck --version
```

### 2단계 — 내려받기

```bash
git clone https://github.com/<계정>/epub3-production.git
cd epub3-production
```

### 3단계 — 파이썬 의존성 (`.hwp` 입력만 해당)

`.hwp`는 `olefile`이 필요합니다. `.hwpx` · `.md` · `.docx` · `.txt`만 쓴다면 건너뛰어도 됩니다.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`.venv`를 폴더 안에 만들면 스크립트가 알아서 찾아 씁니다. 그냥 `python3`로 실행해도 됩니다.

## 사용법

```bash
python3 scripts/build_epub.py 원고.hwp \
  --title "책 제목" \
  --author "저자" \
  --publisher "출판사" \
  --language ko-KR \
  --cover 표지.png \
  --output "책제목_v1.0.epub"
```

### 주요 옵션

| 옵션 | 설명 |
| --- | --- |
| `--title` `--author` | 필수. EPUB 메타데이터 |
| `--language` | 기본 `ko-KR` |
| `--cover` | 세로형 JPG/PNG. 권장 1600×2560 |
| `--drop-leading N` | 본문 앞 N개 문단 제외 (표지와 중복되는 표제지 제거용) |
| `--keep-markdown 파일.md` | 중간 Markdown을 남겨 구조 인식 결과를 확인 |
| `--toc-depth` | 목차 깊이. 기본 2 |
| `--skip-check` | epubcheck 생략 (배포용 완료로 보지 않음) |

### 변환 전 확인을 권합니다

HWP·TXT는 제목 계층 정보가 없어 패턴으로 추정합니다. 먼저 중간 결과를 보세요.

```bash
python3 scripts/build_epub.py 원고.hwp --title "제목" --author "저자" \
  --keep-markdown 확인.md --output 임시.epub
```

`확인.md`에서 `#`(장)과 `##`(절)이 의도대로 붙었는지 보고, 아니면 원고의 제목 표기를
손본 뒤 다시 돌립니다.

## 입력별 동작

| 입력 | 구조 인식 | 비고 |
| --- | --- | --- |
| Markdown | `#` 장, `##` 절 | pandoc이 직접 읽음 |
| DOCX | Heading 1~3 | pandoc이 직접 읽음 |
| HWP | `N장.` `제 N장` `Chapter N` + 원고 내 목차 대조 | `olefile` 필요 |
| HWPX | 위와 동일 | 추가 설치 불필요 |
| TXT | 장 제목 패턴만 승격 | 빈 줄이 문단 구분 |

## 제약

- **표·이미지·글상자는 변환되지 않습니다.** EPUB은 화면 크기에 따라 문장이 흐르는
  리플로우 형식이라 인쇄 조판은 재현 대상이 아닙니다. 신청서·보고서처럼 표 중심 문서는
  EPUB 대상이 아닙니다
- 암호가 걸렸거나 배포용으로 잠긴 HWP는 한글에서 먼저 해제해야 합니다
- 운문 판정은 문단 길이와 문장부호로 추정합니다. 시와 산문이 섞인 원고는
  `--keep-markdown`으로 확인하세요
- `epubcheck` 통과가 모든 리더 앱의 시각 품질을 보장하지는 않습니다
- macOS에서 검증했습니다. Windows·Linux는 미검증입니다

## 문제 해결

| 증상 | 원인·조치 |
| --- | --- |
| `pandoc을 찾지 못했습니다` | 1단계 설치. 또는 `PANDOC_BIN`으로 경로 지정 |
| `epubcheck를 찾지 못했습니다` | `EPUBCHECK_BIN` 또는 `EPUBCHECK_JAR`+`JAVA_BIN` 지정 |
| `olefile이 필요합니다` | 3단계 실행. `.hwp` 입력에만 필요 |
| 장이 하나로 합쳐짐 | 장 제목이 패턴과 다름. `--keep-markdown`으로 확인 후 원고 수정 |
| 시가 문단으로 뭉침 | 원고 안 목차에 작품 제목이 없으면 절로 인식되지 않음 |

## Claude Code 스킬로 쓰기

이 저장소를 스킬 폴더에 두면 Claude Code에서 바로 호출됩니다.

```bash
git clone https://github.com/<계정>/epub3-production.git ~/.claude/skills/epub3-production
```

새 세션부터 `/epub3-production`으로 동작합니다. `SKILL.md`에 절차와 완성 기준이 있습니다.

## 구성

| 경로 | 역할 |
| --- | --- |
| `scripts/build_epub.py` | 변환·검증 진입점 |
| `scripts/hwp5.py` | HWP 5.x 바이너리 본문 추출 |
| `scripts/structure.py` | 문단 → Markdown 구조화 |
| `templates/epub.css` | 한국어 본문 스타일 |
| `SKILL.md` | Claude Code 스킬 정의 |

## 라이선스

MIT. 자세한 내용은 [LICENSE](LICENSE).

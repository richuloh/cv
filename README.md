# Richul Oh — bilingual CV website

ORCID `0000-0003-3221-5121`의 공개 논문을 자동으로 가져와 한글·영문 웹페이지와 PDF CV를 함께 만드는 GitHub Pages 프로젝트입니다. 별도의 서버, 데이터베이스, 유료 API 키가 필요하지 않습니다.

## 가장 쉬운 수정 방법: CV 편집기

Windows에서는 [`CV_편집기_실행.cmd`](CV_편집기_실행.cmd)를 더블클릭하세요. 브라우저에 입력 화면이 자동으로 열립니다.

1. **공통 정보**에서 ORCID, 이메일, 주소를 수정합니다.
2. **한글 CV**, **English CV**에서 현재 소속과 경력을 수정합니다.
3. 경력·학력·연구·수상은 `항목 추가`, `복제`, `삭제`, `↑`, `↓` 버튼으로 관리합니다.
4. **논문 표시** 탭에서 공동 1저자(Co-first)·공동 교신저자(Co-corresponding) 논문에 체크하면 웹사이트의 "주저자 논문" 목록에 `*`와 함께 표시됩니다. 목록 맨 앞 저자로 등록된 논문은 자동으로 체크됩니다.
5. **저장하고 다시 만들기**를 누르면 자동 백업 → ORCID 동기화 → 사이트 생성 → 한·영 PDF 생성 → 검증이 순서대로 실행됩니다.
6. 왼쪽의 미리보기 링크로 결과를 확인합니다.

편집기는 `127.0.0.1`에만 열리고, 실행할 때마다 임의의 보안 토큰을 사용합니다. 입력 화면과 자동 백업 폴더는 GitHub Pages에 배포되지 않습니다. macOS/Linux 또는 터미널에서는 다음 명령으로 실행할 수 있습니다.

```powershell
python scripts/editor_server.py
```

## 현재 구성

- 한글 페이지: `/index.html`
- 영문 페이지: `/en/index.html`
- 한글 PDF: `/downloads/richul-oh-cv-ko.pdf`
- 영문 PDF: `/downloads/richul-oh-cv-en.pdf`
- ORCID 공개 논문, 저자, 저널, DOI 자동 동기화
- 매월 1일 오전 4시 23분(Asia/Seoul) 자동 빌드·배포
- 수동 실행 및 `main` 브랜치 변경 시에도 즉시 재배포

GitHub Pages 자체는 정적 호스팅이지만, GitHub Actions가 매달 ORCID를 읽고 사이트와 PDF를 다시 만든 뒤 Pages에 배포합니다.

## 가장 자주 수정할 파일

소속, 직책, 연락처처럼 직접 관리할 정보는 아래 세 파일에만 있습니다.

| 파일 | 수정 내용 |
| --- | --- |
| `content/profile.json` | ORCID, 이메일, 주소, 사진, 외부 링크 |
| `content/cv.ko.json` | 한글 소개, 경력, 학력, 연구과제, 수상, 발표 |
| `content/cv.en.json` | 영문 소개, 경력, 학력, 연구과제, 수상, 발표 |
| `content/publication_overrides.json` | 공동 1저자·공동 교신저자 수동 표시 (편집기의 **논문 표시** 탭 사용을 권장) |

예를 들어 소속이 바뀌면 두 CV 파일의 `role`, `affiliation`, `experience`를 수정하고 GitHub에 올리면 됩니다. 논문 목록은 `data/orcid.json`을 직접 고치지 말고 ORCID 레코드를 업데이트하세요.

전화번호는 공개 저장소와 웹사이트에 노출하지 않습니다. 원본 CV가 있는 `과거/` 폴더도 `.gitignore`에서 제외되어 있습니다.

## 로컬에서 다시 만들기

Python 3.10 이상과 Chrome/Edge 중 하나가 필요합니다. 외부 Python 패키지는 사용하지 않습니다.

```powershell
python scripts/sync_orcid.py
python scripts/build_site.py
python scripts/render_pdfs.py
python scripts/check_output.py
python -m http.server 8000 --directory dist
```

마지막 명령 후 `http://localhost:8000`에서 확인할 수 있습니다.

## GitHub Pages 배포

1. GitHub에서 새 공개 저장소를 만듭니다. 사용자 대표 페이지라면 저장소 이름을 `<GitHub아이디>.github.io`로, 프로젝트 페이지라면 원하는 이름으로 정합니다.
2. 이 폴더의 프로젝트 파일을 `main` 브랜치에 올립니다. `과거/`, `dist/`, `preview/`는 올리지 않습니다.
3. 저장소의 **Settings → Pages → Build and deployment → Source**에서 **GitHub Actions**를 선택합니다.
4. **Actions** 탭에서 `Sync ORCID and deploy CV`가 성공했는지 확인합니다.

워크플로는 예약 실행 때 최신 `data/orcid.json` 스냅샷을 커밋합니다. 이렇게 하면 변경 기록을 남기고, 장기간 아무 활동이 없는 공개 저장소의 예약 워크플로가 비활성화되는 문제도 피할 수 있습니다. 브랜치 보호 규칙을 추가한다면 `github-actions[bot]`의 스냅샷 푸시가 허용되도록 설정해야 합니다.

## ORCID 동기화 범위

`scripts/sync_orcid.py`는 ORCID Public API v3.0에서 공개로 설정된 정보만 읽습니다.

- 논문 제목, 저자, 저널, 출판일, DOI/PubMed 링크
- 공개 employment/education/qualification 스냅샷

웹사이트의 경력·학력은 문맥과 번역 품질을 유지하기 위해 수동 CV JSON을 우선 사용합니다. ORCID에 비공개로 설정했거나 아직 등록하지 않은 논문은 자동 목록에 나타나지 않습니다.

## 프로젝트 구조

```text
assets/                  스타일, 동작, 프로필 사진
content/                 직접 수정하는 한·영 CV 원본
data/orcid.json          자동 생성되는 ORCID 스냅샷
scripts/sync_orcid.py    ORCID 동기화
scripts/build_site.py    정적 사이트 생성
scripts/render_pdfs.py   Chrome/Edge 기반 PDF 생성
scripts/check_output.py  링크·PDF 무결성 검사
.github/workflows/       월간 동기화와 Pages 배포
editor/                  로컬 전용 브라우저 입력 화면
.editor-backups/         편집기로 저장할 때 생성되는 자동 백업
dist/                    로컬 빌드 결과(저장소에는 올리지 않음)
```

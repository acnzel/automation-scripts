# Vercel 배포 가이드 - 온콜 스케줄 Slack Slash Command

이 가이드는 Slack slash command `/온콜리스트`를 위한 웹훅 API를 Vercel에 배포하는 방법을 안내합니다.

## 📋 개요

- **Slack 명령어**: `/온콜리스트`
- **기능**: Supabase의 `oncall_rotation` 테이블에서 오늘부터 30일간의 온콜 스케줄 조회
- **응답**: Slack 채널에 공개적으로 표시 (in_channel)
- **기술 스택**: Node.js + Vercel Serverless Functions

## 🚀 1단계: 의존성 설치

```bash
npm install
```

## 📦 2단계: Vercel 프로젝트 배포

### 방법 A: Vercel Dashboard (권장)

1. https://vercel.com 접속 및 로그인
2. "Add New..." → "Project" 클릭
3. GitHub 저장소 연결 및 선택
4. 프로젝트 설정:
   - **Framework Preset**: Other
   - **Root Directory**: `./` (기본값)
5. **Environment Variables** 설정 (중요!):
   ```
   SUPABASE_URL = your_supabase_url
   SUPABASE_KEY = your_supabase_key
   ```
6. "Deploy" 클릭

### 방법 B: Vercel CLI

```bash
# Vercel CLI 설치
npm install -g vercel

# 로그인
vercel login

# 프로젝트 초기 배포
vercel

# 환경변수 설정
vercel env add SUPABASE_URL
vercel env add SUPABASE_KEY

# 프로덕션 배포
vercel --prod
```

배포 완료 후 다음과 같은 URL을 받게 됩니다:
```
https://your-project-name.vercel.app/api/oncall
```

## 🔧 3단계: Slack Slash Command 설정

### 1. Slack 앱 생성 또는 선택

1. https://api.slack.com/apps 접속
2. 기존 앱 선택 또는 "Create New App" 클릭
   - "From scratch" 선택
   - App Name 입력 (예: "온콜 스케줄")
   - 워크스페이스 선택

### 2. Slash Command 생성

1. 좌측 메뉴 "Slash Commands" 선택
2. "Create New Command" 클릭
3. 명령어 설정:
   ```
   Command: /온콜리스트
   Request URL: https://your-project-name.vercel.app/api/oncall
   Short Description: 향후 30일간의 온콜 스케줄 조회
   Usage Hint: (비워두기)
   Escape channels, users, and links sent to your app: 체크 해제
   ```
4. "Save" 클릭

### 3. 워크스페이스에 앱 설치

1. 좌측 메뉴 "Install App" 선택
2. "Install to Workspace" 클릭
3. 권한 승인

## ✅ 4단계: 테스트

Slack 채널에서 다음 명령어를 입력하여 테스트:

```
/온콜리스트
```

정상적으로 작동하면 향후 30일간의 온콜 스케줄이 표시됩니다.

## 🧪 로컬 테스트

로컬에서 개발 및 테스트하려면:

```bash
# 개발 서버 시작
npm run dev

# 브라우저에서 접속
# http://localhost:3000/api/oncall
```

curl로 POST 요청 테스트:
```bash
curl -X POST http://localhost:3000/api/oncall \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "token=test&command=/온콜리스트"
```

## 🔄 코드 업데이트

코드 수정 후 배포:

```bash
# Git push (GitHub 연동 시 자동 배포)
git add .
git commit -m "Update oncall webhook"
git push

# 또는 Vercel CLI 사용
vercel --prod
```

## 🐛 문제 해결

### 1. "Application error occurred" 메시지

**원인**: 서버 에러 발생

**해결 방법**:
1. Vercel Dashboard → 프로젝트 선택 → "Deployments"
2. 최신 배포 선택 → "Functions" 탭
3. `oncall` 함수 로그 확인
4. 에러 메시지 확인 후 수정

### 2. 환경변수 설정 오류

**원인**: SUPABASE_URL 또는 SUPABASE_KEY 미설정

**해결 방법**:
```bash
# Vercel Dashboard에서 확인
Settings → Environment Variables

# 또는 CLI로 확인
vercel env ls

# 환경변수 추가
vercel env add SUPABASE_URL
vercel env add SUPABASE_KEY

# 재배포
vercel --prod
```

### 3. Slash Command가 작동하지 않음

**체크리스트**:
- [ ] Request URL이 정확한가? (`https://your-project.vercel.app/api/oncall`)
- [ ] Slack 앱이 워크스페이스에 설치되어 있는가?
- [ ] Vercel 배포가 성공했는가?
- [ ] 환경변수가 제대로 설정되어 있는가?

### 4. 데이터가 조회되지 않음

**원인**: Supabase 연결 또는 테이블 구조 문제

**해결 방법**:
1. Supabase Dashboard에서 `oncall_rotation` 테이블 확인
2. 테이블 구조 확인:
   - `date` (text 또는 date): YYYY-MM-DD 형식
   - `member` (text): 담당자 이름
3. RLS(Row Level Security) 정책 확인
4. 서비스 role key 사용 여부 확인

## 📁 파일 구조

```
scripts/
├── api/
│   └── oncall.js          # Vercel Serverless Function
├── automation/            # Python 스크립트들
│   └── ...
├── package.json           # Node.js 의존성
├── vercel.json           # Vercel 설정
├── .gitignore            # Git 제외 파일
└── VERCEL_SETUP.md       # 이 문서
```

## 📚 추가 자료

- [Vercel Serverless Functions 문서](https://vercel.com/docs/functions)
- [Slack Slash Commands 가이드](https://api.slack.com/interactivity/slash-commands)
- [Slack Block Kit Builder](https://api.slack.com/block-kit/building)
- [Supabase JavaScript Client](https://supabase.com/docs/reference/javascript/introduction)

## 💡 팁

- Slash command는 3초 이내에 응답해야 합니다
- 복잡한 작업은 비동기 처리 후 `response_url`로 응답하세요
- Block Kit을 활용하면 더 풍부한 UI를 만들 수 있습니다

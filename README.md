# Document Search & Chat System

AI 기반 문서 검색 및 채팅 시스템입니다. 문서를 업로드하고 내용을 검색하거나 AI와 채팅을 통해 문서에 대한 질문을 할 수 있습니다.

## 🚀 주요 기능

- **📁 문서 업로드**: PDF, DOCX, TXT, MD 파일 지원
- **🔍 문서 검색**: 업로드된 문서 내용에서 키워드 검색
- **🤖 AI 채팅**: Ollama를 활용한 문서 기반 질답
- **📋 문서 관리**: 업로드된 문서 목록 조회 및 삭제

## 🛠️ 기술 스택

- **Backend**: FastAPI (Python 3.13.5)
- **Frontend**: HTML, CSS, JavaScript
- **AI**: Ollama (llama3.2:1b)
- **문서 처리**: PyPDF2, python-docx
- **UI**: Bootstrap 기반 반응형 디자인

## 📦 설치 및 실행

### 1. 프로젝트 클론

bash git clone <repository-url> cd document-search-chat

### 2. 가상환경 생성 및 활성화
bash python -m venv venv
# Windows
venv\Scripts\activate

### 3. 의존성 설치
bash pip install -r requirements.txt


### 4. Ollama 설치 및 모델 다운로드
bash
# Ollama 설치 ([https://ollama.ai/](https://ollama.ai/))
ollama pull llama3.2:1b


### 5. 환경 변수 설정
`.env` 파일을 확인하고 필요에 따라 수정:
```dotenv
# 서버 설정
HOST=0.0.0.0
PORT=8004
DEBUG=True

# Ollama 설정
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b

# 업로드 설정
MAX_FILE_SIZE=10485760
ALLOWED_EXTENSIONS=.pdf,.docx,.txt,.md
```
### 6. 애플리케이션 실행

python main.py


document-search-chat/
├── app/                    # 애플리케이션 모듈
├── backend/               # 백엔드 로직
├── data/                  # 데이터 저장소
│   ├── chroma_db/         # 벡터 DB (추후 구현)
│   ├── embeddings/        # 임베딩 데이터
│   ├── processed/         # 처리된 문서 메타데이터
│   └── uploads/           # 업로드된 원본 파일
├── docs/                  # 문서
├── logs/                  # 로그 파일
├── processed/             # 처리된 문서 JSON 파일
├── static/                # 정적 파일 (CSS, JS)
├── templates/             # HTML 템플릿
├── tests/                 # 테스트 파일
├── uploads/               # 업로드된 파일
├── .env                   # 환경 변수
├── .gitignore            # Git 제외 파일
├── main.py               # 메인 애플리케이션
├── README.md             # 프로젝트 설명서
└── requirements.txt      # Python 의존성

## 🔧 API 엔드포인트

### 문서 업로드
``` 
POST /upload
Content-Type: multipart/form-data
Body: file (binary)
```

### 문서 목록 조회
``` 
GET /documents
Response: { "documents": [...] }
```

### 문서 검색
``` 
POST /search
Content-Type: application/json
Body: { "query": "검색어" }
```

### AI 채팅
``` 
POST /chat
Content-Type: application/json
Body: { "question": "질문 내용" }
```

### 문서 삭제
``` 
DELETE /documents/{document_id}
```

## 📋 지원 파일 형식
- **PDF**: `.pdf`
- **Microsoft Word**: `.docx`
- **텍스트 파일**: `.txt`
- **마크다운**: `.md`

## 💾 파일 저장 방식
- **원본 파일**: `uploads/` 디렉토리에 저장
- **처리된 데이터**: `processed/` 디렉토리에 JSON 형태로 저장
- **메타데이터**: 파일명, 크기, 업로드 시간, 내용 등 포함

## 🎯 사용 방법
1. **문서 업로드**: 업로드 탭에서 파일을 드래그하거나 선택하여 업로드
2. **문서 검색**: 검색 탭에서 키워드를 입력하여 문서 내용 검색
3. **AI 채팅**: 채팅 탭에서 업로드된 문서에 대한 질문
4. **문서 관리**: 문서 목록 탭에서 업로드된 파일 확인 및 삭제

## ⚠️ 주의사항!
- Ollama 서버가 실행 중이어야 AI 채팅 기능을 사용할 수 있습니다
- 최대 파일 크기: 10MB
- 문서 처리 시간은 파일 크기에 따라 달라질 수 있습니다

## 🔮 향후 개발 계획
- [ ] 벡터 데이터베이스 (ChromaDB) 통합
- [ ] 더 정확한 의미 검색 구현
- [ ] 다중 파일 업로드 지원
- [ ] 문서 미리보기 기능
- [ ] 사용자 인증 시스템
- [ ] 검색 결과 하이라이팅 개선

## 📄 라이선스
이 프로젝트는 MIT 라이선스 하에 제공됩니다.
## 🤝 기여하기
버그 리포트, 기능 제안, 풀 리퀘스트를 환영합니다!
## 📞 문의
프로젝트에 대한 문의사항이 있으시면 이슈를 생성해 주세요.

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import sys
from typing import List, Dict, Any
import json
import aiofiles
from datetime import datetime
import PyPDF2
import hashlib
import re
from app.services.vector_search import create_vector_search_engine

# 벡터 검색 엔진 초기화
vector_engine = create_vector_search_engine()


# FastAPI 앱 생성
app = FastAPI(title="Document Search & Chat System", version="1.0.0")

# 정적 파일과 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 디렉토리 설정
UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Ollama 설정
OLLAMA_HOST = "http://localhost:11434"
MODEL_NAME = "llama3.2:1b"

# 문서 처리 클래스
class DocumentProcessor:
    def __init__(self):
        pass
    
    def generate_document_id(self, filename: str) -> str:
        timestamp = str(int(datetime.now().timestamp() * 1000))
        unique_string = f"{filename}_{timestamp}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:12]
    
    async def extract_pdf_text(self, file_path: str) -> str:
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            raise Exception(f"PDF 텍스트 추출 실패: {str(e)}")
    
    async def extract_txt_text(self, file_path: str) -> str:
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return content.strip()
        except UnicodeDecodeError:
            try:
                async with aiofiles.open(file_path, 'r', encoding='cp949') as f:
                    content = await f.read()
                    return content.strip()
            except:
                async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
                    content = await f.read()
                    return content.strip()
    
    async def extract_docx_text(self, file_path: str) -> str:
        try:
            from docx import Document
            doc = Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            return '\n'.join(text)
        except Exception as e:
            raise Exception(f"DOCX 텍스트 추출 실패: {str(e)}")



    async def process_file(self, file: UploadFile) -> Dict[str, Any]:
        try:
            if not file.filename:
                raise ValueError("파일 이름이 없습니다.")

            # 파일 저장
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)

            ext = file.filename.lower().split('.')[-1]
            
            if ext == 'pdf':
                content = await self.extract_pdf_text(file_path)
            elif ext in ['txt', 'md']:
                content = await self.extract_txt_text(file_path)
            elif ext == 'docx':
                content = await self.extract_docx_text(file_path)
            else:
                raise ValueError(f"지원하지 않는 파일 형식: {ext}")
            
            file_stats = os.stat(file_path)
            document_id = self.generate_document_id(file.filename)
            
            metadata = {
                'id': document_id,
                'filename': file.filename,
                'content': content,
                'size': file_stats.st_size,
                'upload_time': datetime.now().isoformat(),
                'file_type': ext,
                'word_count': len(content.split()),
                'char_count': len(content),
                'filepath': file_path
            }
            
            processed_file_path = os.path.join(PROCESSED_DIR, f"{document_id}.json")
            async with aiofiles.open(processed_file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(metadata, ensure_ascii=False, indent=2))
            
            return metadata
            
        except Exception as e:
            raise Exception(f"파일 처리 중 오류: {str(e)}")

# 전역 인스턴스
doc_processor = DocumentProcessor()

# 라우트들
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일 이름이 없습니다.")

    # 파일 처리
    doc_data = await doc_processor.process_file(file)

    # (수정) 벡터 데이터베이스에 문서 추가
    try:
        vector_engine.add_document(
            document_id=doc_data["id"],
            content=doc_data["content"],
            metadata=doc_data
        )
    except Exception as e:
        # 만약 벡터 DB 추가에 실패하면 이미 저장된 파일을 정리
        if os.path.exists(doc_data['filepath']):
            os.remove(doc_data['filepath'])
        if os.path.exists(os.path.join(PROCESSED_DIR, f"{doc_data['id']}.json")):
            os.remove(os.path.join(PROCESSED_DIR, f"{doc_data['id']}.json"))
        raise HTTPException(status_code=500, detail=f"문서 벡터화 실패: {e}")

    return JSONResponse(
        status_code=201,
        content={
            "message": "파일 업로드 및 처리 성공",
            "document": doc_data
        }
    )

@app.get("/api/documents")
async def get_documents():
    try:
        documents = []
        for filename in os.listdir(PROCESSED_DIR):
            if filename.endswith('.json'):
                file_path = os.path.join(PROCESSED_DIR, filename)
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    doc_data = json.loads(content)
                    doc_summary = {k: v for k, v in doc_data.items() if k != 'content'}
                    documents.append(doc_summary)
        
        documents.sort(key=lambda x: x['upload_time'], reverse=True)
        return JSONResponse({"documents": documents})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 목록 조회 실패: {str(e)}")

@app.post("/api/search")
async def search_documents(request: Request):
    try:
        data = await request.json()
        query = data.get("query", "").strip()

        if not query:
            raise HTTPException(status_code=400, detail="검색어를 입력해주세요.")

        # 벡터 검색을 통해 의미적으로 유사한 문서 조각을 검색합니다.
        vector_results = vector_engine.search_documents(
            query=query,
            n_results=10,
            score_threshold=0.3 # 유사도 점수 임계값
        )

        # 프론트엔드에서 사용할 형식으로 검색 결과를 가공합니다.
        results = []
        for res in vector_results:
            metadata = res.get('metadata', {})
            # content_snippet 키를 사용하여 프론트엔드에 전달합니다.
            snippet = res.get('content', '')
            highlighted_snippet = re.sub(
                re.escape(query),
                f"<mark>{query}</mark>",
                snippet,
                flags=re.IGNORECASE
            )
            
            results.append({
                "id": metadata.get("id"),
                "filename": metadata.get("filename"),
                "file_type": metadata.get("file_type"),
                "upload_time": metadata.get("upload_time"),
                "content_snippet": highlighted_snippet # JS에서 사용하는 키
            })

        return JSONResponse({
            "query": query,
            "results": results,
            "total_results": len(results) # JS에서 사용하는 키
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")

@app.post("/api/chat")
async def chat_with_documents(request: Request):
    try:
        import requests
        
        data = await request.json()
        question = data.get("message", "").strip()  # "question" → "message"로 변경
        
        if not question:
            raise HTTPException(status_code=400, detail="질문을 입력해주세요.")
        
        # 1. 벡터 검색으로 질문과 가장 관련 높은 문서 조각(chunk)을 찾습니다.
        relevant_chunks = vector_engine.search_documents(
            query=question,
            n_results=5,  # AI에게 전달할 가장 관련성 높은 조각 5개
            score_threshold=0.4
        )
        
        if not relevant_chunks:
            return JSONResponse({
                "response": "업로드된 문서에서 질문과 관련된 정보를 찾을 수 없습니다.",  # "answer" → "response"로 변경
                "sources": []
            })
            
        # 2. 검색된 조각들을 바탕으로 AI에게 전달할 컨텍스트(context)를 구성합니다.
        context_parts = []
        source_filenames = set()
        for chunk in relevant_chunks:
            metadata = chunk.get('metadata', {})
            filename = metadata.get('filename', '알 수 없는 파일')
            context_parts.append(f"문서명: {filename}\n내용:\n{chunk['content']}")
            source_filenames.add(filename)
            
        context = "\n\n---\n\n".join(context_parts)
        
        # 3. 구성된 컨텍스트를 기반으로 AI에게 질문합니다.
        prompt = f"""당신은 문서 분석 전문가입니다. 아래 제공된 문서 내용을 바탕으로 질문에 대해 상세하고 친절하게 답변해주세요.

[제공된 문서 내용]
{context}

[질문]
{question}

[답변 조건]
- 반드시 제공된 문서 내용에 근거하여 답변해야 합니다.
- 문서에 관련 내용이 없으면 "제공된 문서의 내용만으로는 답변하기 어렵습니다."라고 솔직하게 답변하세요.
- 답변은 한국어로 작성해주세요.
- 개인정보, 신원 확인서 등의 용어가 나오면 반드시 문서의 정확한 내용을 기반으로 답변하세요."""

        ollama_response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            },
            timeout=60  # 응답 시간을 넉넉하게 설정
        )
        
        ollama_response.raise_for_status()
        
        ai_response = ollama_response.json()
        answer = ai_response.get("response", "오류: 답변을 생성할 수 없습니다.")
        
        return JSONResponse({
            "response": answer,  # "answer" → "response"로 변경
            "sources": sorted(list(source_filenames))
        })
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"AI 모델 서버에 연결할 수 없습니다: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 처리 중 오류 발생: {str(e)}")

@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    # JSON 파일 경로
    json_path = os.path.join(PROCESSED_DIR, f"{document_id}.json")

    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    try:
        # 원본 파일 경로 찾기 및 삭제
        async with aiofiles.open(json_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            doc_data = json.loads(content)
        
        original_filepath = doc_data.get('filepath')
        if original_filepath and os.path.exists(original_filepath):
            os.remove(original_filepath)
        
        # JSON 파일 삭제
        os.remove(json_path)
        
        # (수정) 벡터 데이터베이스에서 문서 삭제
        vector_engine.remove_document(document_id=document_id)

        return JSONResponse(content={"message": f"문서(ID: {document_id})가 성공적으로 삭제되었습니다."})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 삭제 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    print("🚀 Document Search & Chat System 시작!")
    print(f"📍 URL: http://localhost:8004")
    print(f"🤖 Ollama Host: {OLLAMA_HOST}")
    print(f"📝 Model: {MODEL_NAME}")
    print("=" * 50)
    
    uvicorn.run(app, host="localhost", port=8004, log_level="info")
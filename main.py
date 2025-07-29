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



    async def process_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        try:
            ext = filename.lower().split('.')[-1]
            
            if ext == 'pdf':
                content = await self.extract_pdf_text(file_path)
            elif ext in ['txt', 'md']:
                content = await self.extract_txt_text(file_path)
            elif ext == 'docx':
                content = await self.extract_docx_text(file_path)
            else:
                raise ValueError(f"지원하지 않는 파일 형식: {ext}")
            
            file_stats = os.stat(file_path)
            document_id = self.generate_document_id(filename)
            
            metadata = {
                'id': document_id,
                'filename': filename,
                'content': content,
                'size': file_stats.st_size,
                'upload_time': datetime.now().isoformat(),
                'file_type': ext,
                'word_count': len(content.split()),
                'char_count': len(content)
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

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="파일이 선택되지 않았습니다.")
        
        # 파일 형식 확인
        allowed_extensions = {'pdf', 'txt', 'docx', 'md'}
        file_ext = file.filename.lower().split('.')[-1]
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_extensions)}"
            )
        
        # 파일 저장
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # 파일 처리
        metadata = await doc_processor.process_file(file_path, file.filename)
        
        return JSONResponse({
            "success": True,
            "message": "파일이 업로드되고 처리되었습니다.",
            "document": {
                "id": metadata["id"],
                "filename": metadata["filename"],
                "size": metadata["size"],
                "file_type": metadata["file_type"],
                "word_count": metadata["word_count"],
                "upload_time": metadata["upload_time"]
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents")
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

@app.post("/search")
async def search_documents(request: Request):
    try:
        data = await request.json()
        query = data.get("query", "").strip()
        
        if not query:
            raise HTTPException(status_code=400, detail="검색어를 입력해주세요.")
        
        results = []
        for filename in os.listdir(PROCESSED_DIR):
            if filename.endswith('.json'):
                file_path = os.path.join(PROCESSED_DIR, filename)
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    doc_data = json.loads(content)
                    
                    if query.lower() in doc_data['content'].lower():
                        # 검색어 주변 컨텍스트 추출
                        content_lower = doc_data['content'].lower()
                        query_lower = query.lower()
                        
                        matches = []
                        start = 0
                        while True:
                            pos = content_lower.find(query_lower, start)
                            if pos == -1:
                                break
                            
                            # 앞뒤 50자씩 추출
                            context_start = max(0, pos - 50)
                            context_end = min(len(doc_data['content']), pos + len(query) + 50)
                            context = doc_data['content'][context_start:context_end]
                            
                            # 검색어 하이라이트
                            highlighted = re.sub(
                                re.escape(query), 
                                f"<mark>{query}</mark>", 
                                context, 
                                flags=re.IGNORECASE
                            )
                            
                            matches.append(highlighted)
                            start = pos + 1
                            
                            if len(matches) >= 3:  # 최대 3개 매치만 표시
                                break
                        
                        results.append({
                            "id": doc_data["id"],
                            "filename": doc_data["filename"],
                            "file_type": doc_data["file_type"],
                            "upload_time": doc_data["upload_time"],
                            "matches": matches[:3]
                        })
        
        return JSONResponse({
            "query": query,
            "results": results,
            "total": len(results)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")

@app.post("/chat")
async def chat_with_documents(request: Request):
    try:
        import requests
        
        data = await request.json()
        question = data.get("question", "").strip()
        
        if not question:
            raise HTTPException(status_code=400, detail="질문을 입력해주세요.")
        
        # 모든 문서 내용 수집
        all_content = []
        for filename in os.listdir(PROCESSED_DIR):
            if filename.endswith('.json'):
                file_path = os.path.join(PROCESSED_DIR, filename)
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    doc_data = json.loads(content)
                    all_content.append(f"[{doc_data['filename']}]\n{doc_data['content']}")
        
        if not all_content:
            return JSONResponse({
                "question": question,
                "answer": "업로드된 문서가 없습니다. 먼저 문서를 업로드해주세요.",
                "sources": []
            })
        
        # 컨텍스트 준비
        context = "\n\n".join(all_content)
        if len(context) > 4000:  # 토큰 제한을 위해 길이 제한
            context = context[:4000] + "..."
        
        # Ollama에 요청
        prompt = f"""다음 문서들을 기반으로 질문에 답변해주세요:

문서 내용:
{context}

질문: {question}

답변은 한국어로 해주시고, 문서의 내용을 기반으로 정확하게 답변해주세요. 문서에서 답을 찾을 수 없다면 그렇게 말해주세요."""

        ollama_response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        
        if ollama_response.status_code != 200:
            raise HTTPException(status_code=500, detail="AI 모델 응답 오류")
        
        ai_response = ollama_response.json()
        answer = ai_response.get("response", "응답을 생성할 수 없습니다.")
        
        return JSONResponse({
            "question": question,
            "answer": answer,
            "sources": [filename.replace('.json', '') for filename in os.listdir(PROCESSED_DIR) if filename.endswith('.json')]
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 실패: {str(e)}")

@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    try:
        processed_file = os.path.join(PROCESSED_DIR, f"{document_id}.json")
        if not os.path.exists(processed_file):
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        
        os.remove(processed_file)
        
        # 원본 파일도 찾아서 삭제
        for filename in os.listdir(UPLOAD_DIR):
            if document_id in filename:
                original_file = os.path.join(UPLOAD_DIR, filename)
                if os.path.exists(original_file):
                    os.remove(original_file)
                    break
        
        return JSONResponse({"success": True, "message": "문서가 삭제되었습니다."})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 삭제 실패: {str(e)}")

if __name__ == "__main__":
    print("🚀 Document Search & Chat System 시작!")
    print(f"📍 URL: http://localhost:8004")
    print(f"🤖 Ollama Host: {OLLAMA_HOST}")
    print(f"📝 Model: {MODEL_NAME}")
    print("=" * 50)
    
    uvicorn.run(app, host="localhost", port=8004, log_level="info")

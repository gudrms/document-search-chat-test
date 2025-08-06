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
import logging
from app.services.vector_search import create_vector_search_engine

# 메모리 관리 개선
import gc
# 문서 처리 설정
MAX_CHUNK_SIZE = 1000  # 문자 단위
MAX_MEMORY_USAGE = 8  # GB 단위
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB 제한

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name%)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# logs 디렉토리 생성
os.makedirs("logs", exist_ok=True)

# 벡터 엔진 초기화에 예외 처리 추가
try:
    logger.info("벡터 검색 엔진 초기화 시작")
    vector_engine = create_vector_search_engine()
    logger.info("벡터 검색 엔진 초기화 완료")
except Exception as e:
    logger.error(f"벡터 엔진 초기화 실패: {e}")
    # 백업 처리 또는 안전 모드로 실행
    vector_engine = None

# FastAPI 앱 생성
app = FastAPI(title="Document Search & Chat System", version="1.0.0")
logger.info("FastAPI 앱 생성 완료")

# 정적 파일과 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 디렉토리 설정
UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
logger.info("업로드 및 처리 디렉토리 생성 완료")

# Ollama 설정
OLLAMA_HOST = "http://localhost:11434"
MODEL_NAME = "llama3.2:1b"

# 문서 처리 클래스
class DocumentProcessor:
    def __init__(self):
        logger.info("DocumentProcessor 초기화")

    def generate_document_id(self, filename: str) -> str:
        timestamp = str(int(datetime.now().timestamp() * 1000))
        unique_string = f"{filename}_{timestamp}"
        doc_id = hashlib.md5(unique_string.encode()).hexdigest()[:12]
        logger.debug(f"문서 ID 생성: {doc_id} (파일: {filename})")
        return doc_id

    async def extract_pdf_text(self, file_path: str) -> str:
        logger.info(f"PDF 텍스트 추출 시작: {file_path}")
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page_num, page in enumerate(pdf_reader.pages):
                    text += page.extract_text() + "\n"
                    logger.debug(f"PDF 페이지 {page_num + 1} 텍스트 추출 완료")

                logger.info(f"PDF 텍스트 추출 완료: {len(text)} 문자")
                return text.strip()
        except Exception as e:
            logger.error(f"PDF 텍스트 추출 실패: {file_path} - {str(e)}")
            raise Exception(f"PDF 텍스트 추출 실패: {str(e)}")

    async def extract_txt_text(self, file_path: str) -> str:
        logger.info(f"텍스트 파일 추출 시작: {file_path}")
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                logger.info(f"UTF-8로 텍스트 파일 읽기 완료: {len(content)} 문자")
                return content.strip()
        except UnicodeDecodeError:
            logger.warning(f"UTF-8 인코딩 실패, CP949로 재시도: {file_path}")
            try:
                async with aiofiles.open(file_path, 'r', encoding='cp949') as f:
                    content = await f.read()
                    logger.info(f"CP949로 텍스트 파일 읽기 완료: {len(content)} 문자")
                    return content.strip()
            except:
                logger.warning(f"CP949 인코딩 실패, latin-1로 재시도: {file_path}")
                async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
                    content = await f.read()
                    logger.info(f"latin-1로 텍스트 파일 읽기 완료: {len(content)} 문자")
                    return content.strip()

    async def extract_docx_text(self, file_path: str) -> str:
        logger.info(f"DOCX 텍스트 추출 시작: {file_path}")
        try:
            from docx import Document
            doc = Document(file_path)
            text = []
            for para_num, paragraph in enumerate(doc.paragraphs):
                text.append(paragraph.text)
                logger.debug(f"DOCX 단락 {para_num + 1} 추출 완료")

            content = '\n'.join(text)
            logger.info(f"DOCX 텍스트 추출 완료: {len(content)} 문자")
            return content
        except Exception as e:
            logger.error(f"DOCX 텍스트 추출 실패: {file_path} - {str(e)}")
            raise Exception(f"DOCX 텍스트 추출 실패: {str(e)}")

    async def process_file(self, file: UploadFile) -> Dict[str, Any]:
        logger.info(f"📝 [파일 처리] 시작 - {file.filename}")
        try:
            if not file.filename:
                logger.error("❌ [처리 실패] 파일 이름이 없음")
                raise ValueError("파일 이름이 없습니다.")

            # 파일 저장
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            logger.info(f"💾 [파일 저장] 경로: {file_path}")

            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)

            logger.info(f"✅ [저장 완료] 크기: {len(content):,} bytes")

            ext = file.filename.lower().split('.')[-1]
            logger.info(f"📄 [파일 형식] {ext.upper()}")

            # 텍스트 추출
            text_extract_start = datetime.now()
            if ext == 'pdf':
                content = await self.extract_pdf_text(file_path)
            elif ext in ['txt', 'md']:
                content = await self.extract_txt_text(file_path)
            elif ext == 'docx':
                content = await self.extract_docx_text(file_path)
            else:
                logger.error(f"❌ [지원하지 않는 형식] {ext}")
                raise ValueError(f"지원하지 않는 파일 형식: {ext}")

            text_extract_time = (datetime.now() - text_extract_start).total_seconds()
            logger.info(f"⏱️ [텍스트 추출 완료] {text_extract_time:.2f}초 소요")

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
            logger.info(f"💾 [메타데이터 저장] {processed_file_path}")

            async with aiofiles.open(processed_file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(metadata, ensure_ascii=False, indent=2))

            logger.info(f"✅ [처리 완료] ID: {document_id}")
            logger.info(f"📊 [문서 통계] 단어: {metadata['word_count']:,}개, 문자: {metadata['char_count']:,}개")
            return metadata

        except Exception as e:
            logger.error(f"💥 [처리 실패] 파일: {file.filename} - 오류: {str(e)}")
            raise Exception(f"파일 처리 중 오류: {str(e)}")

# 전역 인스턴스
doc_processor = DocumentProcessor()

# 라우트들
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    logger.info("홈페이지 요청")
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    upload_start_time = datetime.now()
    logger.info(f"📤 [업로드 시작] 파일: {file.filename}, 시작시간: {upload_start_time.strftime('%H:%M:%S')}")

    if not file.filename:
        logger.error("❌ [업로드 실패] 파일 이름이 없는 업로드 요청")
        raise HTTPException(status_code=400, detail="파일 이름이 없습니다.")

    try:
        # 파일 크기 체크 추가
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)
        logger.info(f"📊 [파일 정보] 크기: {file_size_mb:.2f}MB ({len(content):,} bytes)")

        # 파일 포인터를 처음으로 되돌리기
        await file.seek(0)

        # 파일 처리
        logger.info("🔄 [처리 중] 파일 분석 및 텍스트 추출 시작")
        doc_data = await doc_processor.process_file(file)

        # 벡터 데이터베이스에 문서 추가
        logger.info(f"🔍 [벡터화 시작] 문서 ID: {doc_data['id']}")
        try:
            vector_engine.add_document(
                document_id=doc_data["id"],
                content=doc_data["content"],
                metadata=doc_data
            )
            logger.info(f"✅ [벡터화 성공] 문서 ID: {doc_data['id']}")
        except Exception as e:
            logger.error(f"❌ [벡터화 실패] 문서 ID: {doc_data['id']} - 오류: {str(e)}")
            # 만약 벡터 DB 추가에 실패하면 이미 저장된 파일을 정리
            if os.path.exists(doc_data['filepath']):
                os.remove(doc_data['filepath'])
                logger.info(f"🧹 [정리 완료] 원본 파일: {doc_data['filepath']}")
            if os.path.exists(os.path.join(PROCESSED_DIR, f"{doc_data['id']}.json")):
                os.remove(os.path.join(PROCESSED_DIR, f"{doc_data['id']}.json"))
                logger.info(f"🧹 [정리 완료] 메타데이터: {doc_data['id']}.json")
            raise HTTPException(status_code=500, detail=f"문서 벡터화 실패: {e}")

        # 성공 로그
        upload_end_time = datetime.now()
        processing_time = (upload_end_time - upload_start_time).total_seconds()

        logger.info(f"🎉 [업로드 성공] 파일: {file.filename}")
        logger.info(f"📋 [처리 결과] ID: {doc_data['id']}, 단어: {doc_data['word_count']:,}개, 문자: {doc_data['char_count']:,}개")
        logger.info(f"⏱️ [처리 시간] {processing_time:.2f}초")

        return JSONResponse(
            status_code=201,
            content={
                "message": "파일 업로드 및 처리 성공",
                "document": doc_data
            }
        )

    except HTTPException:
        # HTTPException은 그대로 재발생
        raise
    except Exception as e:
        upload_end_time = datetime.now()
        processing_time = (upload_end_time - upload_start_time).total_seconds()

        logger.error(f"💥 [업로드 실패] 파일: {file.filename}")
        logger.error(f"❌ [오류 내용] {str(e)}")
        logger.error(f"⏱️ [실패까지 시간] {processing_time:.2f}초")

        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {str(e)}")

@app.get("/api/documents")
async def get_documents():
    logger.info("문서 목록 조회 요청")
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
        logger.info(f"문서 목록 조회 완료: {len(documents)}개")
        return JSONResponse({"documents": documents})

    except Exception as e:
        logger.error(f"문서 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"문서 목록 조회 실패: {str(e)}")

@app.post("/api/search")
async def search_documents(request: Request):
    logger.info("문서 검색 요청")
    try:
        data = await request.json()
        query = data.get("query", "").strip()
        logger.info(f"검색어: '{query}'")

        if not query:
            logger.warning("빈 검색어로 요청")
            raise HTTPException(status_code=400, detail="검색어를 입력해주세요.")

        # 벡터 검색을 통해 의미적으로 유사한 문서 조각을 검색합니다.
        logger.info("벡터 검색 시작")
        vector_results = vector_engine.search_documents(
            query=query,
            n_results=10,
            score_threshold=None  # 동적 임계값 사용
        )
        logger.info(f"벡터 검색 완료: {len(vector_results)}개 결과")

        # 결과 처리
        results = []
        for res in vector_results:
            metadata = res.get('metadata', {})
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
                "content_snippet": highlighted_snippet,
                "similarity": res.get('similarity', 0),  # 유사도 정보 추가
                "threshold_used": res.get('threshold_used', 0)  # 사용된 임계값 추가
            })

        logger.info(f"검색 결과 처리 완료: {len(results)}개")
        return JSONResponse({
            "query": query,
            "results": results,
            "total_results": len(results)
        })

    except Exception as e:
        logger.error(f"검색 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")

@app.post("/api/chat")
async def chat_with_documents(request: Request):
    logger.info("채팅 요청")
    try:
        import requests

        data = await request.json()
        question = data.get("message", "").strip()
        logger.info(f"질문: '{question}'")

        if not question:
            logger.warning("빈 질문으로 요청")
            raise HTTPException(status_code=400, detail="질문을 입력해주세요.")

        # 1. 벡터 검색으로 질문과 가장 관련 높은 문서 조각(chunk)을 찾습니다.
        logger.info(f"벡터 DB 문서 수: {len(vector_engine.list_documents())}")
        logger.info(f"검색 전 컬렉션 상태: {vector_engine.get_collection_stats()}")
        logger.info("관련 문서 조각 검색 시작")
        relevant_chunks = vector_engine.search_documents(
            query=question,
            n_results=5,
            score_threshold=None
        )
        logger.info(f"관련 문서 조각 검색 완료: {len(relevant_chunks)}개")

        if not relevant_chunks:
            logger.info("관련 문서를 찾을 수 없음")
            return JSONResponse({
                "response": "업로드된 문서에서 질문과 관련된 정보를 찾을 수 없습니다. 다른 키워드로 검색해보세요.",
                "sources": []
            })

        # 2. 중복 제거 및 품질 향상된 컨텍스트 구성
        logger.info("컨텍스트 구성 시작")
        context_parts = []
        source_filenames = set()
        for chunk in relevant_chunks:
            metadata = chunk.get('metadata', {})
            filename = metadata.get('filename', '알 수 없는 파일')
            context_parts.append(f"문서명: {filename}\n내용:\n{chunk['content']}")
            source_filenames.add(filename)

        context = "\n\n---\n\n".join(context_parts)
        logger.info(f"컨텍스트 구성 완료: {len(context_parts)}개 조각, {len(source_filenames)}개 파일")

        # 3. 구성된 컨텍스트를 기반으로 AI에게 질문합니다.
        prompt = f"""당신은 문서 분석 전문가입니다. 아래 제공된 문서 내용을 바탕으로 질문에 대해 상세하고 친절하게 답변해주세요.

[제공된 문서 내용]
{context}

[질문]
{question}

[답변 지침]
1. 반드시 제공된 문서 내용만을 근거로 답변하세요
2. 문서에서 직접적으로 관련된 내용이 없으면 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답변하세요
3. 답변할 때는 구체적인 내용과 절차를 포함하세요
4. 불확실하거나 추측성 정보는 포함하지 마세요
5. 한국어로 명확하고 이해하기 쉽게 답변하세요

답변:"""

        logger.info("Ollama AI에 요청 전송")
        ollama_response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # 창의성 줄이고 정확성 향상
                    "top_p": 0.9
                }
            },
            timeout=60
        )

        ollama_response.raise_for_status()
        logger.info("Ollama AI 응답 수신 완료")

        ai_response = ollama_response.json()
        answer = ai_response.get("response", "오류: 답변을 생성할 수 없습니다.")

        logger.info(f"채팅 응답 완료: {len(answer)} 문자, 출처: {sorted(list(source_filenames))}")
        return JSONResponse({
            "response": answer,
            "sources": sorted(list(source_filenames))
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"AI 모델 서버 연결 실패: {str(e)}")
        raise HTTPException(status_code=503, detail=f"AI 모델 서버에 연결할 수 없습니다: {e}")
    except Exception as e:
        logger.error(f"채팅 처리 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"채팅 처리 중 오류 발생: {str(e)}")

@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    logger.info(f"문서 삭제 요청: {document_id}")

    # JSON 파일 경로
    json_path = os.path.join(PROCESSED_DIR, f"{document_id}.json")

    if not os.path.exists(json_path):
        logger.error(f"삭제할 문서를 찾을 수 없음: {document_id}")
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    try:
        # 원본 파일 경로 찾기 및 삭제
        logger.info(f"메타데이터 파일 읽기: {json_path}")
        async with aiofiles.open(json_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            doc_data = json.loads(content)

        original_filepath = doc_data.get('filepath')
        if original_filepath and os.path.exists(original_filepath):
            os.remove(original_filepath)
            logger.info(f"원본 파일 삭제 완료: {original_filepath}")

        # JSON 파일 삭제
        os.remove(json_path)
        logger.info(f"메타데이터 파일 삭제 완료: {json_path}")

        # 벡터 데이터베이스에서 문서 삭제
        logger.info(f"벡터 데이터베이스에서 문서 삭제 시작: {document_id}")
        vector_engine.remove_document(document_id=document_id)
        logger.info(f"벡터 데이터베이스에서 문서 삭제 완료: {document_id}")

        logger.info(f"문서 삭제 완료: {document_id}")
        return JSONResponse(content={"message": f"문서(ID: {document_id})가 성공적으로 삭제되었습니다."})

    except Exception as e:
        logger.error(f"문서 삭제 중 오류 발생: {document_id} - {str(e)}")
        raise HTTPException(status_code=500, detail=f"문서 삭제 중 오류 발생: {str(e)}")

# 디버깅을 위한 임시 라우트 추가
@app.get("/api/debug/vector-stats")
async def get_vector_stats():
    """벡터 DB 상태 디버깅용"""
    try:
        stats = vector_engine.get_collection_stats()
        documents = vector_engine.list_documents()
        return JSONResponse({
            "stats": stats,
            "document_ids": documents,
            "total_documents": len(documents)
        })
    except Exception as e:
        return JSONResponse({"error": str(e)})

if __name__ == "__main__":
    print("🚀 Document Search & Chat System 시작!")
    print(f"📍 URL: http://localhost:8004")
    print(f"🤖 Ollama Host: {OLLAMA_HOST}")
    print(f"📝 Model: {MODEL_NAME}")
    print("=" * 50)

    logger.info("애플리케이션 서버 시작")
    uvicorn.run(app, host="localhost", port=8004, log_level="info")
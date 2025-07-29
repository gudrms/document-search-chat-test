// 전역 변수
let documents = [];
let isLoading = false;

// DOMContentLoaded에서 모든 이벤트 리스너 등록
document.addEventListener("DOMContentLoaded", function() {
    loadDocuments();
    initializeEventListeners();
    
    // Enter 키 이벤트 설정
    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
        searchInput.addEventListener("keypress", function(e) {
            if (e.key === "Enter") {
                searchDocuments();
            }
        });
    }
});

function initializeEventListeners() {
    // 탭 버튼들
    document.querySelectorAll('[data-tab]').forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            showTab(tabName);
        });
    });
    
    // 파일 선택 버튼
    const uploadBtn = document.querySelector('.upload-btn');
    if (uploadBtn) {
        uploadBtn.addEventListener('click', function() {
            document.getElementById('fileInput').click();
        });
    }
    
    // 검색 버튼
    const searchBtn = document.querySelector('.search-btn');
    if (searchBtn) {
        searchBtn.addEventListener('click', searchDocuments);
    }
    
    // 채팅 전송 버튼
    const sendBtn = document.querySelector('.send-btn');
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
    
    // 채팅 입력 엔터키
    const chatInput = document.getElementById("chatInput");
    if (chatInput) {
        chatInput.addEventListener("keypress", function(e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // 드래그 앤 드롭 초기화
    initializeDragDrop();
}

// 동적으로 생성되는 삭제 버튼을 위한 이벤트 위임
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('document-delete')) {
        const docId = e.target.getAttribute('data-doc-id');
        if (docId) {
            deleteDocument(docId);
        }
    }
});

// 탭 전환 함수
function showTab(tabName) {
    // 모든 탭 콘텐츠 숨기기
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
    });
    
    // 모든 탭 버튼 비활성화
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // 선택된 탭 콘텐츠 표시
    const targetTab = document.getElementById(tabName + '-tab');
    if (targetTab) {
        targetTab.style.display = 'block';
    }
    
    // 클릭된 탭 버튼 활성화
    const clickedTab = document.querySelector(`[data-tab="${tabName}"]`);
    if (clickedTab) {
        clickedTab.classList.add('active');
    }
    
    // 문서 목록 탭인 경우 문서 목록 로드
    if (tabName === 'documents') {
        loadDocuments();
    }
}

// 드래그 앤 드롭 초기화
function initializeDragDrop() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');

    if (!uploadArea || !fileInput) return;

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            uploadSingleFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadSingleFile(e.target.files[0]);
        }
    });
}

// 단일 파일 업로드
async function uploadSingleFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    showLoading(true);
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            const docInfo = result.document || result;
            document.getElementById('uploadResult').innerHTML = `
                <div class="alert alert-success">
                    <h5>✅ 업로드 성공!</h5>
                    <p><strong>파일:</strong> ${docInfo.filename}</p>
                    <p><strong>크기:</strong> ${formatFileSize(docInfo.size)}</p>
                    <p><strong>단어 수:</strong> ${docInfo.word_count || 'N/A'}</p>
                    <p><strong>업로드 시간:</strong> ${formatDate(docInfo.upload_time)}</p>
                </div>
            `;
            showAlert("파일이 업로드되었습니다.", "success");
            await loadDocuments();
        } else {
            throw new Error(result.detail || '업로드 실패');
        }
    } catch (error) {
        document.getElementById('uploadResult').innerHTML = `
            <div class="alert alert-danger">
                <h5>❌ 업로드 실패</h5>
                <p>${error.message}</p>
            </div>
        `;
        showAlert("업로드 실패: " + error.message, "danger");
    }
    
    showLoading(false);
    
    // 파일 입력 초기화
    document.getElementById('fileInput').value = '';
}

// 문서 목록 로드
async function loadDocuments() {
    try {
        const response = await fetch("/api/documents");
        const data = await response.json();
        documents = data.documents || [];
        
        const documentsList = document.getElementById("documentsList");
        
        if (documents.length === 0) {
            documentsList.innerHTML = "<p class=\"text-muted\">업로드된 문서가 없습니다.</p>";
            return;
        }
        
        let html = "";
        documents.forEach(doc => {
            html += `
                <div class="card mb-3">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h6 class="card-title">${doc.filename}</h6>
                                <small class="text-muted">
                                    ${formatFileSize(doc.size)} | ${formatDate(doc.upload_time)}
                                </small>
                            </div>
                            <button class="btn btn-sm btn-outline-danger document-delete" 
                                    data-doc-id="${doc.id}" title="삭제">
                                🗑️
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });
        
        documentsList.innerHTML = html;
        
    } catch (error) {
        showAlert("문서 목록을 불러오는데 실패했습니다.", "danger");
    }
}

// 문서 검색
async function searchDocuments() {
    const query = document.getElementById("searchInput").value.trim();
    
    if (!query) {
        showAlert("검색어를 입력해주세요.", "warning");
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch("/api/search", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ query: query, max_results: 10 })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            displaySearchResults(result);
        } else {
            showAlert("검색 실패: " + result.detail, "danger");
        }
    } catch (error) {
        showAlert("검색 중 오류: " + error.message, "danger");
    }
    
    showLoading(false);
}

// 검색 결과 표시
function displaySearchResults(result) {
    const searchResults = document.getElementById("searchResults");
    
    if (result.total_results === 0) {
        searchResults.innerHTML = `
            <div class="text-center mt-5">
                <i class="fas fa-search fa-3x text-muted mb-3"></i>
                <h5>검색 결과가 없습니다</h5>
                <p class="text-muted">다른 검색어를 시도해보세요.</p>
            </div>
        `;
        return;
    }
    
    let html = `
        <div class="mb-3">
            <h6>검색 결과: ${result.total_results}개</h6>
        </div>
    `;
    
    result.results.forEach(item => {
        html += `
            <div class="card mb-3">
                <div class="card-body">
                    <h6 class="card-title">📄 ${item.filename}</h6>
                    <div class="card-text">${item.content_snippet}</div>
                </div>
            </div>
        `;
    });
    
    searchResults.innerHTML = html;
}

// AI 채팅
async function sendMessage() {
    const chatInput = document.getElementById("chatInput");
    const message = chatInput.value.trim();
    
    if (!message) {
        return;
    }
    
    // 사용자 메시지 표시
    addMessageToChat(message, "user");
    chatInput.value = "";
    
    // 로딩 메시지 표시
    const loadingId = addMessageToChat("답변을 생성하고 있습니다...", "bot", true);
    
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message: message })
        });
        
        const result = await response.json();
        
        // 로딩 메시지 제거
        removeMessage(loadingId);
        
        if (response.ok) {
            // AI 응답 표시
            addMessageToChat(result.response, "bot", false, result.sources);
        } else {
            addMessageToChat("오류: " + result.detail, "bot");
        }
    } catch (error) {
        removeMessage(loadingId);
        addMessageToChat("오류: " + error.message, "bot");
    }
}

// 채팅 메시지 추가
function addMessageToChat(content, sender, isLoading = false, sources = null) {
    const chatMessages = document.getElementById("chatMessages");
    const messageId = "msg_" + Date.now();
    
    let sourcesHtml = "";
    if (sources && sources.length > 0) {
        sourcesHtml = `<div class="small text-muted mt-2">출처: ${sources.join(", ")}</div>`;
    }
    
    let loadingSpinner = "";
    if (isLoading) {
        loadingSpinner = '<span class="spinner-border spinner-border-sm me-2"></span>';
    }
    
    const messageClass = sender === "user" ? "text-end" : "text-start";
    const bgClass = sender === "user" ? "bg-primary text-white" : "bg-light";
    
    const messageHtml = `
        <div class="mb-3 ${messageClass}" id="${messageId}">
            <div class="d-inline-block p-3 rounded ${bgClass}" style="max-width: 70%;">
                ${loadingSpinner}${content}
                ${sourcesHtml}
            </div>
        </div>
    `;
    
    chatMessages.insertAdjacentHTML("beforeend", messageHtml);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageId;
}

// 메시지 제거
function removeMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.remove();
    }
}

// 문서 삭제
async function deleteDocument(docId) {
    if (!confirm("정말 이 문서를 삭제하시겠습니까?")) {
        return;
    }
    
    try {
        const response = await fetch("/api/documents/" + docId, {
            method: "DELETE"
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert("문서가 삭제되었습니다.", "success");
            await loadDocuments();
        } else {
            showAlert("삭제 실패: " + result.detail, "danger");
        }
    } catch (error) {
        showAlert("삭제 중 오류: " + error.message, "danger");
    }
}

// 유틸리티 함수들
function showLoading(show) {
    const loadingModal = document.getElementById("loadingModal");
    if (!loadingModal) return;
    
    if (show) {
        const modal = new bootstrap.Modal(loadingModal);
        modal.show();
    } else {
        const modalInstance = bootstrap.Modal.getInstance(loadingModal);
        if (modalInstance) {
            modalInstance.hide();
        }
    }
}

function showAlert(message, type) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show position-fixed" 
             style="top: 20px; right: 20px; z-index: 9999;" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.insertAdjacentHTML("beforeend", alertHtml);
    
    // 5초 후 자동 제거
    setTimeout(function() {
        const alerts = document.querySelectorAll(".alert");
        if (alerts.length > 0) {
            alerts[alerts.length - 1].remove();
        }
    }, 5000);
}

function formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString("ko-KR") + " " + date.toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit"
    });
}
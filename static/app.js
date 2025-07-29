// 전역 변수
let documents = [];
let isLoading = false;

// 페이지 로드 시 초기화
document.addEventListener("DOMContentLoaded", function() {
    loadDocuments();
    
    // Enter 키 이벤트 설정
    document.getElementById("searchInput").addEventListener("keypress", function(e) {
        if (e.key === "Enter") {
            searchDocuments();
        }
    });
});

// 파일 업로드
async function uploadFiles() {
    const fileInput = document.getElementById("fileInput");
    const files = fileInput.files;
    
    if (files.length === 0) {
        showAlert("파일을 선택해주세요.", "warning");
        return;
    }
    
    showLoading(true);
    
    for (let file of files) {
        try {
            const formData = new FormData();
            formData.append("file", file);
            
            const response = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok) {
                showAlert("파일 \"" + file.name + "\"이 업로드되었습니다.", "success");
            } else {
                showAlert("파일 \"" + file.name + "\" 업로드 실패: " + result.detail, "danger");
            }
        } catch (error) {
            showAlert("파일 \"" + file.name + "\" 업로드 중 오류: " + error.message, "danger");
        }
    }
    
    // 파일 입력 초기화 및 문서 목록 새로고침
    fileInput.value = "";
    await loadDocuments();
    showLoading(false);
}
// 문서 목록 로드
async function loadDocuments() {
    try {
        const response = await fetch("/api/documents");
        documents = await response.json();
        
        const documentsList = document.getElementById("documentsList");
        
        if (documents.length === 0) {
            documentsList.innerHTML = "<p class=\"text-muted\">업로드된 문서가 없습니다.</p>";
            return;
        }
        
        let html = "";
        documents.forEach(doc => {
            html += "<div class=\"document-item fade-in\">";
            html += "<button class=\"document-delete\" onclick=\"deleteDocument('" + doc.id + "')\" title=\"삭제\">";
            html += "<i class=\"fas fa-times\"></i>";
            html += "</button>";
            html += "<div class=\"document-name\">" + doc.filename + "</div>";
            html += "<div class=\"document-info\">";
            html += formatFileSize(doc.size) + " | " + formatDate(doc.upload_time);
            html += "</div>";
            html += "</div>";
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
        searchResults.innerHTML = "<div class=\"text-center\">" +
            "<i class=\"fas fa-search fa-3x text-muted mb-3\"></i>" +
            "<h5>검색 결과가 없습니다</h5>" +
            "<p class=\"text-muted\">다른 검색어를 시도해보세요.</p>" +
            "</div>";
        return;
    }
    
    let html = "<div class=\"mb-3\">" +
        "<h6>검색 결과: " + result.total_results + "개</h6>" +
        "</div>";
    
    result.results.forEach(item => {
        html += "<div class=\"search-result-item slide-in\">";
        html += "<div class=\"result-filename\">";
        html += "<i class=\"fas fa-file-alt\"></i> " + item.filename;
        html += "</div>";
        html += "<div class=\"result-snippet\">";
        html += highlightSearchTerm(item.content_snippet, result.query);
        html += "</div>";
        html += "</div>";
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
function addMessageToChat(content, sender, isLoading, sources) {
    const chatMessages = document.getElementById("chatMessages");
    const messageId = "msg_" + Date.now();
    
    let sourcesHtml = "";
    if (sources && sources.length > 0) {
        sourcesHtml = "<div class=\"message-sources\">출처: " + sources.join(", ") + "</div>";
    }
    
    let loadingSpinner = "";
    if (isLoading) {
        loadingSpinner = "<span class=\"spinner-border spinner-border-sm me-2\"></span>";
    }
    
    const messageHtml = "<div class=\"message " + sender + "-message slide-in\" id=\"" + messageId + "\">" +
        "<div class=\"message-content\">" +
        loadingSpinner + content +
        sourcesHtml +
        "</div>" +
        "</div>";
    
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

// 채팅 Enter 키 처리
function handleChatEnter(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
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
    const loadingModal = new bootstrap.Modal(document.getElementById("loadingModal"));
    if (show) {
        loadingModal.show();
    } else {
        loadingModal.hide();
    }
}

function showAlert(message, type) {
    const alertHtml = "<div class=\"alert alert-" + type + " alert-dismissible fade show\" role=\"alert\">" +
        message +
        "<button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\"></button>" +
        "</div>";
    
    document.body.insertAdjacentHTML("afterbegin", alertHtml);
    
    // 5초 후 자동 제거
    setTimeout(function() {
        const alert = document.querySelector(".alert");
        if (alert) {
            alert.remove();
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

function highlightSearchTerm(text, searchTerm) {
    if (!searchTerm) return text;
    const regex = new RegExp("(" + searchTerm + ")", "gi");
    return text.replace(regex, "<span class=\"result-highlight\">$1</span>");
}

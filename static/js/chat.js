// ==============================
// ELEMENTS
// ==============================

const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const chatBody = document.getElementById("chatBody");
const newChatBtn = document.querySelector(".new-chat-btn");

// Modal Elements
const uploadModal = document.getElementById("uploadModal");
const openUploadModalBtn = document.getElementById("openUploadModalBtn");
const closeUploadModalBtn = document.getElementById("closeUploadModalBtn");
const pdfInput = document.getElementById("pdfFile");
const currentPdf = document.getElementById("currentPdf");
const dropZone = document.getElementById("dropZone");
const uploadProgress = document.getElementById("uploadProgress");
const uploadStatusText = document.getElementById("uploadStatusText");

// Sidebar Document List
const documentList = document.getElementById("documentList");

// ==============================
// INITIALIZATION & STATE
// ==============================

let currentSessionId = null;

document.addEventListener("DOMContentLoaded", () => {
    fetchUserDocuments();
    fetchChatSessions();
});

// ==============================
// MODAL LOGIC
// ==============================

openUploadModalBtn.addEventListener("click", (e) => {
    e.preventDefault();
    uploadModal.style.display = "flex";
    currentPdf.innerHTML = "No PDF Selected";
    uploadProgress.style.display = "none";
});

closeUploadModalBtn.addEventListener("click", () => {
    uploadModal.style.display = "none";
});

uploadModal.addEventListener("click", (e) => {
    if (e.target === uploadModal) {
        uploadModal.style.display = "none";
    }
});

// ==============================
// DRAG & DROP LOGIC
// ==============================

dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
        pdfInput.files = e.dataTransfer.files;
        handleFileUpload();
    }
});

pdfInput.addEventListener("change", () => {
    if (pdfInput.files.length) {
        handleFileUpload();
    }
});

// ==============================
// UPLOAD LOGIC
// ==============================

function handleFileUpload() {
    const file = pdfInput.files[0];
    if (!file) return;

    currentPdf.innerHTML = "📄 " + file.name;
    uploadProgress.style.display = "flex";
    uploadStatusText.innerText = "Uploading & Analyzing...";

    const formData = new FormData();
    formData.append("pdf", file);

    fetch("/user/upload", {
        method: "POST",
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        uploadProgress.style.display = "none";
        
        if (data.success) {
            currentPdf.innerHTML = "✅ Upload Successful!";
            setTimeout(() => {
                uploadModal.style.display = "none";
            }, 1000);
            
            addMessage(`Document "${file.name}" uploaded successfully. Now you can ask questions from this document.`, "ai");
            
            // Refresh sidebar list
            fetchUserDocuments();
        } else {
            currentPdf.innerHTML = "❌ Upload Failed";
            alert(data.message || data.error);
        }
    })
    .catch(err => {
        console.error(err);
        uploadProgress.style.display = "none";
        currentPdf.innerHTML = "❌ Upload Failed";
    });
}

// ==============================
// DOCUMENT MANAGEMENT
// ==============================

function fetchChatSessions() {
    fetch("/api/chat/sessions")
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            renderChatSessions(data.sessions);
        }
    })
    .catch(err => console.error("Error fetching sessions:", err));
}

function renderChatSessions(sessions) {
    const sessionList = document.getElementById("sessionList");
    if (!sessionList) return;
    
    sessionList.innerHTML = "";
    
    sessions.forEach(session => {
        const sessionItem = document.createElement("div");
        sessionItem.className = "chat-item";
        sessionItem.id = `session-${session.id}`;
        
        sessionItem.innerHTML = `
            <div class="doc-info" onclick="loadChatSession(${session.id}, '${session.title.replace(/'/g, "\\'")}')">
                <i class="bi bi-chat-left-text"></i>
                <span class="doc-name" title="${session.title}">${session.title}</span>
            </div>
            <button class="delete-doc-btn" onclick="deleteSession(${session.id}, event)" title="Delete Chat">
                <i class="bi bi-trash"></i>
            </button>
        `;
        sessionList.appendChild(sessionItem);
    });
}

function loadChatSession(sessionId, title) {
    currentSessionId = sessionId;
    
    document.querySelectorAll("#sessionList .chat-item").forEach(item => item.classList.remove("active"));
    
    const activeItem = document.getElementById(`session-${sessionId}`);
    if (activeItem) activeItem.classList.add("active");
    
    const shareBtn = document.getElementById("shareChatBtn");
    if (shareBtn) shareBtn.style.display = "block";
    
    fetch(`/api/chat/sessions/${sessionId}`)
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            chatBody.innerHTML = "";
            data.history.forEach(log => {
                addMessage(log.message, "user");
                // The log model doesn't currently store source, but we can display general ai
                addMessage(log.response, "ai"); 
            });
            chatBody.scrollTop = chatBody.scrollHeight;
        }
    })
    .catch(err => console.error("Error loading chat history:", err));
}

function deleteSession(sessionId, event) {
    event.stopPropagation();
    
    if (!confirm("Are you sure you want to delete this chat session? This cannot be undone.")) {
        return;
    }
    
    fetch(`/api/chat/sessions/${sessionId}`, { method: "DELETE" })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            if (currentSessionId === sessionId) {
                // If deleting active session, start a new chat
                startNewChat();
            }
            fetchChatSessions();
        } else {
            alert(data.message);
        }
    })
    .catch(err => console.error(err));
}

function fetchUserDocuments() {
    fetch("/user/documents")
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            renderDocumentList(data.documents);
        }
    })
    .catch(err => console.error("Error fetching documents:", err));
}

function getFileIcon(docType) {
    if (!docType) return '<i class="bi bi-file-earmark-fill" style="color: #6b7280;"></i>';
    
    switch(docType.toLowerCase()) {
        case 'pdf':
            return '<i class="bi bi-file-earmark-pdf-fill" style="color: #ef4444;"></i>';
        case 'xlsx':
        case 'xls':
            return '<i class="bi bi-file-earmark-spreadsheet-fill" style="color: #10b981;"></i>';
        case 'csv':
            return '<i class="bi bi-file-earmark-bar-graph-fill" style="color: #f59e0b;"></i>';
        case 'docx':
        case 'doc':
            return '<i class="bi bi-file-earmark-word-fill" style="color: #3b82f6;"></i>';
        case 'pptx':
        case 'ppt':
            return '<i class="bi bi-file-earmark-play-fill" style="color: #f97316;"></i>';
        default:
            return '<i class="bi bi-file-earmark-fill" style="color: #6b7280;"></i>';
    }
}

let pollIntervals = {};

function renderDocumentList(documents) {
    const searchAllItem = document.getElementById("searchAllDoc");
    documentList.innerHTML = "";
    documentList.appendChild(searchAllItem);
    
    // Clear old pollers
    Object.values(pollIntervals).forEach(clearInterval);
    pollIntervals = {};

    documents.forEach(doc => {
        const docItem = document.createElement("div");
        docItem.className = "chat-item";
        docItem.id = `doc-${doc.file_name}`;
        
        const iconHtml = getFileIcon(doc.doc_type || doc.file_name.split('.').pop());
        
        const displayName = doc.original_name || doc.file_name;
        const uploadDate = doc.uploaded_at ? `<div style="font-size:0.7em;color:#aaa;">${doc.uploaded_at}</div>` : '';
        
        let actionButtons = '';
        if (doc.status === 'Processing') {
            actionButtons = `<span style="font-size:0.8em; color:#f59e0b;"><i class="bi bi-hourglass-split"></i> Processing</span>`;
            
            // Start polling for this doc
            pollIntervals[doc.id] = setInterval(() => {
                fetch(`/user/documents/${doc.id}/status`)
                .then(r => r.json())
                .then(d => {
                    if (d.success && d.status !== 'Processing') {
                        fetchUserDocuments();
                    }
                });
            }, 3000);
        } else {
            actionButtons = `
                <button class="rename-doc-btn" onclick="renameDocument(${doc.id}, '${displayName}', event)" title="Rename Document" style="margin-right:5px;">
                    <i class="bi bi-pencil"></i>
                </button>
                <button class="delete-doc-btn" onclick="deleteDocument(${doc.id}, '${doc.file_name}', event)" title="Delete Document">
                    <i class="bi bi-trash"></i>
                </button>
            `;
        }

        docItem.innerHTML = `
            <div class="doc-info" onclick="setActiveDocument('${doc.file_name}')">
                ${iconHtml}
                <div>
                    <span class="doc-name" title="${displayName}">${displayName}</span>
                    ${uploadDate}
                </div>
            </div>
            <div style="display:flex;">
                ${actionButtons}
            </div>
        `;
        documentList.appendChild(docItem);
    });
}

function renameDocument(doc_id, currentName, event) {
    event.stopPropagation();
    const newName = prompt("Enter new document name:", currentName);
    if (!newName || newName === currentName) return;

    fetch(`/user/documents/${doc_id}/rename`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_name: newName })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) fetchUserDocuments();
        else alert(data.message);
    })
    .catch(err => console.error(err));
}

function setActiveDocument(pdf_name) {
    // Remove active class from all
    document.querySelectorAll(".document-list .chat-item").forEach(item => item.classList.remove("active"));
    
    // Add active class to selected
    if (pdf_name) {
        const activeItem = document.getElementById(`doc-${pdf_name}`);
        if (activeItem) activeItem.classList.add("active");
    } else {
        document.getElementById("searchAllDoc").classList.add("active");
    }
    
    fetch("/user/set-active-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pdf_name: pdf_name })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            if (pdf_name) {
                addMessage(`Switched to document: ${pdf_name}`, "ai");
            } else {
                addMessage(`Switched to Search Across All PDFs mode.`, "ai");
            }
        }
    })
    .catch(err => console.error(err));
}

function deleteDocument(doc_id, pdf_name, event) {
    event.stopPropagation();
    
    if (!confirm(`Are you sure you want to delete ${pdf_name}? This cannot be undone.`)) {
        return;
    }
    
    fetch(`/user/documents/${doc_id}`, { method: "DELETE" })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            addMessage(`Document ${pdf_name} deleted successfully.`, "ai");
            fetchUserDocuments();
            // Automatically switch to Search All if we deleted the active one
            setActiveDocument(null);
        } else {
            alert(data.message);
        }
    })
    .catch(err => console.error(err));
}

// ==============================
// SEND MESSAGE
// ==============================

function sendMessage() {
    const message = input.value.trim();
    if (message === "") return;

    // Remove welcome screen
    const welcome = document.querySelector(".welcome-screen");
    if (welcome) {
        welcome.remove();
    }

    addMessage(message, "user");
    input.value = "";
    showTyping();

    fetch("/api/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: message, session_id: currentSessionId })
    })
    .then(response => response.json())
    .then(data => {
        removeTyping();
        addMessage(data.reply || data.response, "ai", data.source_used); 
        if (data.session_id && currentSessionId === null) {
            currentSessionId = data.session_id;
            const shareBtn = document.getElementById("shareChatBtn");
            if (shareBtn) shareBtn.style.display = "block";
            fetchChatSessions();
        }
    })
    .catch(error => {
        removeTyping();
        addMessage("Something went wrong. Please try again.", "ai");
        console.error(error);
    });
}

function addMessage(text, sender, source=null){
    const message = document.createElement("div");
    message.className = `message ${sender}`;

    const bubble = document.createElement("div");
    bubble.className = "message-content";
    bubble.textContent = text;
    
    if (sender === "ai" && source && source !== "None") {
        const sourceBadge = document.createElement("div");
        sourceBadge.style = "font-size: 0.75rem; color: #a1a1aa; margin-top: 5px;";
        sourceBadge.innerHTML = `<i class="bi bi-info-circle"></i> Source: ${source}`;
        bubble.appendChild(sourceBadge);
    }

    message.appendChild(bubble);

    if(sender === "ai"){
        const actionDiv = document.createElement("div");
        actionDiv.className = "message-actions";

        const listenBtn = document.createElement("button");
        listenBtn.className = "listen-btn";
        listenBtn.innerHTML = "🔊 Listen";
        listenBtn.onclick = () => speakMessage(text, listenBtn);

        actionDiv.appendChild(listenBtn);
        message.appendChild(actionDiv);
    }

    chatBody.appendChild(message);
    chatBody.scrollTop = chatBody.scrollHeight;
}

// ==============================
// AI TYPING
// ==============================

function showTyping() {
    const typing = document.createElement("div");
    typing.className = "message ai typing";
    typing.id = "typing";
    typing.innerHTML = `
        <div class="message-content">
            Thinking...
        </div>
    `;
    chatBody.appendChild(typing);
    chatBody.scrollTop = chatBody.scrollHeight;
}

function removeTyping() {
    const typing = document.getElementById("typing");
    if (typing) {
        typing.remove();
    }
}

// ==============================
// NEW CHAT
// ==============================

function startNewChat() {
    currentSessionId = null;
    
    document.querySelectorAll("#sessionList .chat-item").forEach(item => item.classList.remove("active"));
    const shareBtn = document.getElementById("shareChatBtn");
    if (shareBtn) shareBtn.style.display = "none";
    
    chatBody.innerHTML = `
        <div class="welcome-screen">
            <h1>Hello 👋</h1>
            <p>How can I help you today?</p>
        </div>
    `;
}

newChatBtn.addEventListener("click", startNewChat);

const searchInput = document.getElementById("chatSearchInput");
if (searchInput) {
    searchInput.addEventListener("input", function(e) {
        const term = e.target.value.toLowerCase();
        
        // Filter Sessions
        document.querySelectorAll("#sessionList .chat-item").forEach(item => {
            const text = item.querySelector(".doc-name").innerText.toLowerCase();
            if (text.includes(term)) {
                item.style.display = "flex";
            } else {
                item.style.display = "none";
            }
        });
        
        // Filter Documents
        document.querySelectorAll("#documentList .chat-item:not(#searchAllDoc)").forEach(item => {
            const text = item.querySelector(".doc-name").innerText.toLowerCase();
            if (text.includes(term)) {
                item.style.display = "flex";
            } else {
                item.style.display = "none";
            }
        });
    });
}

const shareChatBtn = document.getElementById("shareChatBtn");
if (shareChatBtn) {
    shareChatBtn.addEventListener("click", () => {
        if (!currentSessionId) return;
        
        let transcript = "";
        document.querySelectorAll(".message").forEach(msg => {
            const isUser = msg.classList.contains("user");
            const text = msg.querySelector(".message-content").innerText.replace(/Source:.*$/g, '');
            transcript += (isUser ? "User: " : "AI: ") + text + "\\n\\n";
        });
        
        navigator.clipboard.writeText(transcript).then(() => {
            alert("Chat transcript copied to clipboard!");
        });
    });
}

// ==============================
// EVENTS
// ==============================

sendBtn.addEventListener("click", sendMessage);

input.addEventListener("keypress", function(e){
    if(e.key === "Enter"){
        sendMessage();
    }
});

function speakMessage(text, button){
    window.speechSynthesis.cancel();
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = "en-IN";
    speech.rate = 1;
    speech.pitch = 1;
    speech.volume = 1;
    button.innerHTML = "⏸ Speaking...";
    speech.onend = function(){
        button.innerHTML = "🔊 Listen";
    };
    window.speechSynthesis.speak(speech);
}

// ==============================
// MOBILE SIDEBAR
// ==============================

const mobileMenuBtn = document.getElementById("mobileMenuBtn");
const sidebar = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebarOverlay");

if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener("click", () => {
        sidebar.classList.add("active");
        sidebarOverlay.classList.add("active");
    });
}

if (sidebarOverlay) {
    sidebarOverlay.addEventListener("click", () => {
        sidebar.classList.remove("active");
        sidebarOverlay.classList.remove("active");
    });
}
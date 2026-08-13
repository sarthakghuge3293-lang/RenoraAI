const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const chatBody = document.getElementById("chatBody");
const newChatBtn = document.querySelector(".new-chat-btn");

const chatVoiceBtn = document.getElementById("chatVoiceBtn");

const inlineVoiceArea =
    document.getElementById("inlineVoiceArea");

const inlineVoiceOrb =
    document.getElementById("inlineVoiceOrb");

const inlineVoiceStatus =
    document.getElementById("inlineVoiceStatus");

const inlineVoiceHint =
    document.getElementById("inlineVoiceHint");

const closeInlineVoiceBtn =
    document.getElementById("closeInlineVoiceBtn");

// Voice mode elements
const voiceMode = document.getElementById("voiceMode");
const voiceCloseBtn = document.getElementById("voiceCloseBtn");
const voiceStopBtn = document.getElementById("voiceStopBtn");
const chatVoiceOrb = document.getElementById("chatVoiceOrb");
const chatVoiceStatus = document.getElementById("chatVoiceStatus");
const chatVoiceHint = document.getElementById("chatVoiceHint");
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

// Voice state
let voiceRecognition = null;
let voiceListening = false;
let voiceSpeaking = false;
let voiceProcessing = false;
let selectedVoiceLanguage = "en-IN";

let speechQueue = [];
let speechIndex = 0;


// ============================================================
// INLINE VOICE CHAT
// ============================================================

function initInlineVoice() {

    if (!chatVoiceBtn || !inlineVoiceArea) {
        console.warn(
            "[Voice] Inline voice elements not found."
        );
        return;
    }

    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {

        chatVoiceBtn.disabled = true;

        chatVoiceBtn.title =
            "Voice is not supported in this browser.";

        return;
    }

    voiceRecognition =
        new SpeechRecognition();

    voiceRecognition.continuous = false;
    voiceRecognition.interimResults = true;
    voiceRecognition.maxAlternatives = 1;
    voiceRecognition.lang =
        selectedVoiceLanguage;

    chatVoiceBtn.addEventListener(
        "click",
        function () {

            openInlineVoice();
        }
    );

    if (closeInlineVoiceBtn) {

        closeInlineVoiceBtn.addEventListener(
            "click",
            function () {

                closeInlineVoice();
            }
        );
    }

    // --------------------------------------------------------
    // MICROPHONE START
    // --------------------------------------------------------

    voiceRecognition.onstart =
        function () {

            voiceListening = true;

            inlineVoiceArea.classList.add(
                "listening"
            );

            inlineVoiceArea.classList.remove(
                "speaking"
            );

            setVoiceStatus(
                "Listening...",
                "Speak naturally"
            );
        };

    // --------------------------------------------------------
    // RESULT
    // --------------------------------------------------------

    voiceRecognition.onresult =
        function (event) {

            let finalText = "";
            let interimText = "";

            for (
                let i = event.resultIndex;
                i < event.results.length;
                i++
            ) {

                const text =
                    event.results[i][0].transcript;

                if (
                    event.results[i].isFinal
                ) {

                    finalText += text;

                } else {

                    interimText += text;
                }
            }

            const displayText =
                (
                    finalText ||
                    interimText ||
                    ""
                ).trim();

            if (displayText) {

                setVoiceStatus(
                    "Listening...",
                    displayText
                );
            }

            if (finalText.trim()) {

                sendVoiceQuestion(
                    finalText.trim()
                );
            }
        };

    // --------------------------------------------------------
    // END
    // --------------------------------------------------------

    voiceRecognition.onend =
        function () {

            voiceListening = false;

            inlineVoiceArea.classList.remove(
                "listening"
            );

            if (
                !voiceProcessing &&
                !voiceSpeaking
            ) {

                setVoiceStatus(
                    "Ready to talk",
                    "Tap the microphone to speak"
                );
            }
        };

    // --------------------------------------------------------
    // ERROR
    // --------------------------------------------------------

    voiceRecognition.onerror =
        function (event) {

            console.error(
                "[Voice] Recognition error:",
                event.error
            );

            voiceListening = false;
            voiceProcessing = false;

            inlineVoiceArea.classList.remove(
                "listening"
            );

            if (
                event.error === "not-allowed"
            ) {

                setVoiceStatus(
                    "Microphone blocked",
                    "Allow microphone access in Chrome."
                );

                return;
            }

            if (
                event.error === "no-speech"
            ) {

                setVoiceStatus(
                    "No speech detected",
                    "Tap the microphone and try again."
                );

                return;
            }

            setVoiceStatus(
                "Voice error",
                "Please try again."
            );
        };
}

// ============================================================
// OPEN VOICE
// ============================================================

function openInlineVoice() {

    if (
        voiceProcessing ||
        voiceListening
    ) {
        return;
    }

    stopCurrentVoiceSpeech();

    inlineVoiceArea.classList.add(
        "active"
    );

    setVoiceStatus(
        "Ready to talk",
        "Listening..."
    );

    startVoiceRecognition();
}

// ============================================================
// START RECOGNITION
// ============================================================


// ============================================================
// CLOSE VOICE
// ============================================================

function closeInlineVoice() {

    stopCurrentVoiceSpeech();

    if (
        voiceRecognition &&
        voiceListening
    ) {

        try {
            voiceRecognition.stop();
        } catch (error) {
            console.warn(error);
        }
    }

    voiceListening = false;
    voiceProcessing = false;

    inlineVoiceArea.classList.remove(
        "active"
    );

    inlineVoiceArea.classList.remove(
        "listening"
    );

    inlineVoiceArea.classList.remove(
        "speaking"
    );
}

// ============================================================
// SEND VOICE QUESTION
// ============================================================

async function sendVoiceQuestion(
    question
) {

    if (!question) {
        return;
    }

    voiceProcessing = true;
    voiceListening = false;

    inlineVoiceArea.classList.remove(
        "listening"
    );

    // Put recognized text into normal input
    input.value = question;

    // Remove welcome
    const welcome =
        document.querySelector(
            ".welcome-screen"
        );

    if (welcome) {
        welcome.remove();
    }

    // Show user's text in chat
    addMessage(
        question,
        "user"
    );

    // Clear input again
    input.value = "";

    // Existing typing UI
    showTyping();

    setVoiceStatus(
        "Thinking...",
        question
    );

    try {

        // IMPORTANT:
        // EXISTING BACKEND ONLY.
        // No backend changes.
        const response =
            await fetch(
                "/api/chat",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    credentials:
                        "same-origin",

                    body: JSON.stringify({
                        message: question,
                        session_id:
                            currentSessionId
                    })
                }
            );

        const data =
            await response.json();

        removeTyping();

        if (
            !response.ok ||
            data.success === false
        ) {

            throw new Error(
                data.reply ||
                data.message ||
                "Unable to get AI response."
            );
        }

        const answer =
            (
                data.reply ||
                data.response ||
                ""
            ).trim();

        if (!answer) {

            throw new Error(
                "AI returned an empty response."
            );
        }

        // -----------------------------------------------------
        // SHOW AI TEXT IN CHAT
        // -----------------------------------------------------

        addMessage(
            answer,
            "ai",
            data.source_used
        );

        // Preserve existing session handling
        if (
            data.session_id &&
            currentSessionId === null
        ) {

            currentSessionId =
                data.session_id;

            const shareBtn =
                document.getElementById(
                    "shareChatBtn"
                );

            if (shareBtn) {
                shareBtn.style.display =
                    "block";
            }

            fetchChatSessions();
        }

        voiceProcessing = false;

        // -----------------------------------------------------
        // READ SAME AI ANSWER
        // -----------------------------------------------------

        speakInlineAnswer(
            answer
        );

    } catch (error) {

        removeTyping();

        voiceProcessing = false;

        console.error(
            "[Voice] Chat error:",
            error
        );

        addMessage(
            "Something went wrong. Please try again.",
            "ai"
        );

        setVoiceStatus(
            "Something went wrong",
            error.message ||
            "Please try again."
        );
    }
}

// ============================================================
// SPEAK AI ANSWER
// ============================================================

function speakInlineAnswer(
    text
) {

    if (
        !("speechSynthesis" in window)
    ) {

        setVoiceStatus(
            "Answer ready",
            text
        );

        return;
    }

    stopCurrentVoiceSpeech();

    voiceQueue =
        splitVoiceText(text);

    voiceQueueIndex = 0;

    if (!voiceQueue.length) {
        return;
    }

    speakNextVoiceSentence();
}

// ============================================================
// SENTENCE SPEECH
// ============================================================

function speakNextVoiceSentence() {

    if (
        voiceQueueIndex >=
        voiceQueue.length
    ) {

        voiceSpeaking = false;

        inlineVoiceArea.classList.remove(
            "speaking"
        );

        setVoiceStatus(
            "Ready to talk",
            "Tap the microphone to speak again"
        );

        // Automatically listen again
        setTimeout(
            function () {

                if (
                    inlineVoiceArea.classList.contains(
                        "active"
                    )
                ) {

                    startVoiceRecognition();
                }

            },
            500
        );

        return;
    }

    const sentence =
        voiceQueue[
            voiceQueueIndex
        ];

    const speech =
        new SpeechSynthesisUtterance(
            sentence
        );

    speech.lang =
        selectedVoiceLanguage;

    // Slow and clear
    speech.rate = 0.82;
    speech.pitch = 1.0;
    speech.volume = 1.0;

    const voices =
        window.speechSynthesis.getVoices();

    const selectedVoice =
        findVoiceForLanguage(
            voices,
            selectedVoiceLanguage
        );

    if (selectedVoice) {
        speech.voice =
            selectedVoice;
    }

    speech.onstart =
        function () {

            voiceSpeaking = true;

            inlineVoiceArea.classList.remove(
                "listening"
            );

            inlineVoiceArea.classList.add(
                "speaking"
            );

            setVoiceStatus(
                "Renvora is speaking...",
                sentence
            );
        };

    speech.onend =
        function () {

            if (!voiceSpeaking) {
                return;
            }

            voiceQueueIndex++;

            setTimeout(
                speakNextVoiceSentence,
                220
            );
        };

    speech.onerror =
        function (error) {

            console.error(
                "[Voice] TTS error:",
                error
            );

            voiceSpeaking = false;

            inlineVoiceArea.classList.remove(
                "speaking"
            );

            setVoiceStatus(
                "Ready to talk",
                "Tap the microphone to speak again"
            );
        };

    if (window.RenvoraTTS) {
        window.RenvoraTTS.postMessage(speech.text);
    } else {
        window.speechSynthesis.speak(speech);
    }
}

// ============================================================
// CLEAN VOICE TEXT
// ============================================================

function cleanVoiceText(
    text
) {

    let cleaned =
        String(text || "");

    cleaned =
        cleaned.replace(
            /https?:\/\/\S+/gi,
            ""
        );

    cleaned =
        cleaned.replace(
            /[*_`#~]/g,
            ""
        );

    cleaned =
        cleaned.replace(
            /^[\s]*[-•▪◦]\s+/gm,
            ""
        );

    cleaned =
        cleaned.replace(
            /\r?\n+/g,
            ". "
        );

    cleaned =
        cleaned.replace(
            /[\[\]\{\}]/g,
            ""
        );

    cleaned =
        cleaned.replace(
            /([.!?।])\1+/g,
            "$1"
        );

    cleaned =
        cleaned.replace(
            /\s+/g,
            " "
        );

    return cleaned.trim();
}

// ============================================================
// SPLIT VOICE TEXT
// ============================================================

function splitVoiceText(
    text
) {

    const cleaned =
        cleanVoiceText(text);

    if (!cleaned) {
        return [];
    }

    return cleaned
        .split(
            /(?<=[.!?।])\s+/
        )
        .map(
            item => item.trim()
        )
        .filter(
            item => item.length > 0
        );
}

// ============================================================
// STOP CURRENT VOICE
// ============================================================

function stopCurrentVoiceSpeech() {

    if (
        "speechSynthesis" in window
    ) {
        window.speechSynthesis.cancel();
    }

    voiceQueue = [];
    voiceQueueIndex = 0;
    voiceSpeaking = false;

    if (inlineVoiceArea) {
        inlineVoiceArea.classList.remove(
            "speaking"
        );
    }
}

// ============================================================
// VOICE STATUS
// ============================================================

function setVoiceStatus(
    status,
    hint
) {

    if (inlineVoiceStatus) {
        inlineVoiceStatus.textContent =
            status;
    }

    if (inlineVoiceHint) {
        inlineVoiceHint.textContent =
            hint || "";
    }
}

// ============================================================
// FIND BEST BROWSER VOICE
// ============================================================

function findVoiceForLanguage(
    voices,
    language
) {

    if (
        !voices ||
        !voices.length
    ) {
        return null;
    }

    const exact =
        voices.find(
            voice =>
                voice.lang &&
                voice.lang.toLowerCase() ===
                language.toLowerCase()
        );

    if (exact) {
        return exact;
    }

    const baseLanguage =
        language
            .split("-")[0]
            .toLowerCase();

    const googleVoice =
        voices.find(
            voice =>
                voice.name &&
                voice.name
                    .toLowerCase()
                    .includes("google") &&
                voice.lang &&
                voice.lang
                    .toLowerCase()
                    .startsWith(
                        baseLanguage
                    )
        );

    if (googleVoice) {
        return googleVoice;
    }

    const sameLanguage =
        voices.find(
            voice =>
                voice.lang &&
                voice.lang
                    .toLowerCase()
                    .startsWith(
                        baseLanguage
                    )
        );

    return (
        sameLanguage ||
        voices[0] ||
        null
    );
}

// ============================================================
// START INLINE VOICE
// ============================================================

// initInlineVoice handled by inline-voice.js

// ==============================
// DOM READY
// ==============================

document.addEventListener("DOMContentLoaded", () => {
    fetchUserDocuments();
    fetchChatSessions();
});

// ==============================
// MODAL LOGIC
// ==============================

if (openUploadModalBtn) {
    openUploadModalBtn.addEventListener("click", (e) => {
        e.preventDefault();

        if (uploadModal) {
            uploadModal.style.display = "flex";
        }

        if (currentPdf) {
            currentPdf.innerHTML = "No PDF Selected";
        }

        if (uploadProgress) {
            uploadProgress.style.display = "none";
        }
    });
}

if (closeUploadModalBtn) {
    closeUploadModalBtn.addEventListener("click", () => {
        if (uploadModal) {
            uploadModal.style.display = "none";
        }
    });
}

if (uploadModal) {
    uploadModal.addEventListener("click", (e) => {
        if (e.target === uploadModal) {
            uploadModal.style.display = "none";
        }
    });
}

// ==============================
// DRAG & DROP LOGIC
// ==============================

if (dropZone) {
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

        if (
            e.dataTransfer &&
            e.dataTransfer.files &&
            e.dataTransfer.files.length
        ) {
            pdfInput.files = e.dataTransfer.files;
            handleFileUpload();
        }
    });
}

if (pdfInput) {
    pdfInput.addEventListener("change", () => {
        if (pdfInput.files.length) {
            handleFileUpload();
        }
    });
}

// ==============================
// UPLOAD LOGIC
// ==============================

function handleFileUpload() {
    const file = pdfInput.files[0];

    if (!file) {
        return;
    }

    if (currentPdf) {
        currentPdf.innerHTML = "📄 " + file.name;
    }

    if (uploadProgress) {
        uploadProgress.style.display = "flex";
    }

    if (uploadStatusText) {
        uploadStatusText.innerText =
            "Uploading & Analyzing...";
    }

    const formData = new FormData();
    formData.append("pdf", file);

    fetch("/user/upload", {
        method: "POST",
        body: formData
    })
        .then(res => res.json())
        .then(data => {

            if (uploadProgress) {
                uploadProgress.style.display = "none";
            }

            if (data.success) {

                if (currentPdf) {
                    currentPdf.innerHTML =
                        "✅ Upload Successful!";
                }

                setTimeout(() => {
                    if (uploadModal) {
                        uploadModal.style.display = "none";
                    }
                }, 1000);

                addMessage(
                    `Document "${file.name}" uploaded successfully. Now you can ask questions from this document.`,
                    "ai"
                );

                fetchUserDocuments();

                setActiveDocument(
                    data.pdf || file.name
                );

            } else {

                if (currentPdf) {
                    currentPdf.innerHTML =
                        "❌ Upload Failed";
                }

                alert(
                    data.message ||
                    data.error ||
                    "Upload failed."
                );
            }
        })
        .catch(err => {

            console.error(err);

            if (uploadProgress) {
                uploadProgress.style.display = "none";
            }

            if (currentPdf) {
                currentPdf.innerHTML =
                    "❌ Upload Failed";
            }

            alert(
                "Unable to upload document."
            );
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
                renderChatSessions(
                    data.sessions
                );
            }
        })
        .catch(err =>
            console.error(
                "Error fetching sessions:",
                err
            )
        );
}

function renderChatSessions(sessions) {

    const sessionList =
        document.getElementById(
            "sessionList"
        );

    if (!sessionList) {
        return;
    }

    sessionList.innerHTML = "";

    sessions.forEach(session => {

        const sessionItem =
            document.createElement("div");

        sessionItem.className =
            "chat-item";

        sessionItem.id =
            `session-${session.id}`;

        const safeTitle =
            String(
                session.title || "Chat"
            ).replace(
                /'/g,
                "\\'"
            );

        sessionItem.innerHTML = `
            <div
                class="doc-info"
                onclick="loadChatSession(${session.id}, '${safeTitle}')"
            >
                <i class="bi bi-chat-left-text"></i>
                <span
                    class="doc-name"
                    title="${escapeHtml(session.title || "Chat")}"
                >
                    ${escapeHtml(session.title || "Chat")}
                </span>
            </div>

            <button
                class="delete-doc-btn"
                onclick="deleteSession(${session.id}, event)"
                title="Delete Chat"
            >
                <i class="bi bi-trash"></i>
            </button>
        `;

        sessionList.appendChild(
            sessionItem
        );
    });
}

function loadChatSession(
    sessionId,
    title
) {

    currentSessionId = sessionId;

    document
        .querySelectorAll(
            "#sessionList .chat-item"
        )
        .forEach(item =>
            item.classList.remove(
                "active"
            )
        );

    const activeItem =
        document.getElementById(
            `session-${sessionId}`
        );

    if (activeItem) {
        activeItem.classList.add(
            "active"
        );
    }

    const shareBtn =
        document.getElementById(
            "shareChatBtn"
        );

    if (shareBtn) {
        shareBtn.style.display =
            "block";
    }

    fetch(
        `/api/chat/sessions/${sessionId}`
    )
        .then(res => res.json())
        .then(data => {

            if (data.success) {

                chatBody.innerHTML = "";

                data.history.forEach(
                    log => {

                        addMessage(
                            log.message,
                            "user"
                        );

                        addMessage(
                            log.response,
                            "ai"
                        );
                    }
                );

                chatBody.scrollTop =
                    chatBody.scrollHeight;
            }
        })
        .catch(err =>
            console.error(
                "Error loading chat history:",
                err
            )
        );
}

function deleteSession(
    sessionId,
    event
) {

    event.stopPropagation();

    if (
        !confirm(
            "Are you sure you want to delete this chat session? This cannot be undone."
        )
    ) {
        return;
    }

    fetch(
        `/api/chat/sessions/${sessionId}`,
        {
            method: "DELETE"
        }
    )
        .then(res => res.json())
        .then(data => {

            if (data.success) {

                if (
                    currentSessionId ===
                    sessionId
                ) {
                    startNewChat();
                }

                fetchChatSessions();

            } else {

                alert(
                    data.message ||
                    "Unable to delete chat."
                );
            }
        })
        .catch(err =>
            console.error(err)
        );
}

function fetchUserDocuments() {

    fetch("/user/documents")
        .then(res => res.json())
        .then(data => {

            if (data.success) {
                renderDocumentList(
                    data.documents
                );
            }
        })
        .catch(err =>
            console.error(
                "Error fetching documents:",
                err
            )
        );
}

function getFileIcon(docType) {

    if (!docType) {
        return '<i class="bi bi-file-earmark-fill" style="color: #6b7280;"></i>';
    }

    switch (
        docType.toLowerCase()
    ) {

        case "pdf":
            return '<i class="bi bi-file-earmark-pdf-fill" style="color: #ef4444;"></i>';

        case "xlsx":
        case "xls":
            return '<i class="bi bi-file-earmark-spreadsheet-fill" style="color: #10b981;"></i>';

        case "csv":
            return '<i class="bi bi-file-earmark-bar-graph-fill" style="color: #f59e0b;"></i>';

        case "docx":
        case "doc":
            return '<i class="bi bi-file-earmark-word-fill" style="color: #3b82f6;"></i>';

        case "pptx":
        case "ppt":
            return '<i class="bi bi-file-earmark-play-fill" style="color: #f97316;"></i>';

        default:
            return '<i class="bi bi-file-earmark-fill" style="color: #6b7280;"></i>';
    }
}

let pollIntervals = {};

function renderDocumentList(
    documents
) {

    const searchAllItem =
        document.getElementById(
            "searchAllDoc"
        );

    if (!documentList) {
        return;
    }

    documentList.innerHTML = "";

    if (searchAllItem) {
        documentList.appendChild(
            searchAllItem
        );
    }

    Object.values(
        pollIntervals
    ).forEach(clearInterval);

    pollIntervals = {};

    documents.forEach(doc => {

        const docItem =
            document.createElement("div");

        docItem.className =
            "chat-item";

        docItem.id =
            `doc-${doc.file_name}`;

        const iconHtml =
            getFileIcon(
                doc.doc_type ||
                (
                    doc.file_name || ""
                )
                    .split(".")
                    .pop()
            );

        const displayName =
            doc.original_name ||
            doc.file_name ||
            "Document";

        const uploadDate =
            doc.uploaded_at
                ? `
                    <div
                        style="
                            font-size:0.7em;
                            color:#aaa;
                        "
                    >
                        ${escapeHtml(
                            doc.uploaded_at
                        )}
                    </div>
                `
                : "";

        let actionButtons = "";

        if (
            doc.status ===
            "Processing"
        ) {

            actionButtons = `
                <span
                    style="
                        font-size:0.8em;
                        color:#f59e0b;
                    "
                >
                    <i class="bi bi-hourglass-split"></i>
                    Processing
                </span>
            `;

            pollIntervals[doc.id] =
                setInterval(() => {

                    fetch(
                        `/user/documents/${doc.id}/status`
                    )
                        .then(r =>
                            r.json()
                        )
                        .then(d => {

                            if (
                                d.success &&
                                d.status !==
                                "Processing"
                            ) {
                                fetchUserDocuments();
                            }
                        });

                }, 3000);

        } else {

            const safeDisplayName =
                String(displayName)
                    .replace(
                        /'/g,
                        "\\'"
                    );

            actionButtons = `
                <button
                    class="rename-doc-btn"
                    onclick="renameDocument(${doc.id}, '${safeDisplayName}', event)"
                    title="Rename Document"
                    style="margin-right:5px;"
                >
                    <i class="bi bi-pencil"></i>
                </button>

                <button
                    class="delete-doc-btn"
                    onclick="deleteDocument(${doc.id}, '${safeDisplayName}', event)"
                    title="Delete Document"
                >
                    <i class="bi bi-trash"></i>
                </button>
            `;
        }

        const safeFileName =
            String(
                doc.file_name || ""
            ).replace(
                /'/g,
                "\\'"
            );

        docItem.innerHTML = `
            <div
                class="doc-info"
                onclick="setActiveDocument('${safeFileName}')"
            >
                ${iconHtml}

                <div>
                    <span
                        class="doc-name"
                        title="${escapeHtml(displayName)}"
                    >
                        ${escapeHtml(displayName)}
                    </span>

                    ${uploadDate}
                </div>
            </div>

            <div
                style="display:flex;"
            >
                ${actionButtons}
            </div>
        `;

        documentList.appendChild(
            docItem
        );
    });
}

function renameDocument(
    doc_id,
    currentName,
    event
) {

    event.stopPropagation();

    const newName =
        prompt(
            "Enter new document name:",
            currentName
        );

    if (
        !newName ||
        newName === currentName
    ) {
        return;
    }

    fetch(
        `/user/documents/${doc_id}/rename`,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify({
                new_name: newName
            })
        }
    )
        .then(res => res.json())
        .then(data => {

            if (data.success) {
                fetchUserDocuments();
            } else {
                alert(
                    data.message ||
                    "Rename failed."
                );
            }
        })
        .catch(err =>
            console.error(err)
        );
}

function setActiveDocument(
    pdf_name
) {

    document
        .querySelectorAll(
            ".document-list .chat-item"
        )
        .forEach(item =>
            item.classList.remove(
                "active"
            )
        );

    if (pdf_name) {

        const activeItem =
            document.getElementById(
                `doc-${pdf_name}`
            );

        if (activeItem) {
            activeItem.classList.add(
                "active"
            );
        }

    } else {

        const searchAll =
            document.getElementById(
                "searchAllDoc"
            );

        if (searchAll) {
            searchAll.classList.add(
                "active"
            );
        }
    }

    if (!currentSessionId) {

        fetch(
            "/api/chat",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    message: "Hello",
                    session_id: null
                })
            }
        )
            .then(res => res.json())
            .then(data => {

                if (
                    data.success &&
                    data.session_id
                ) {

                    currentSessionId =
                        data.session_id;

                    fetchChatSessions();

                    _lockSourceBackend(
                        pdf_name
                    );
                }
            });

        return;
    }

    _lockSourceBackend(
        pdf_name
    );
}

function _lockSourceBackend(
    pdf_name
) {

    let payload = {
        session_id:
            currentSessionId,

        source:
            pdf_name
                ? "uploaded_document"
                : "renvora_knowledge"
    };

    if (pdf_name) {
        payload.doc_name =
            pdf_name;
    }

    fetch(
        "/api/chat/lock-source",
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify(
                payload
            )
        }
    )
        .then(res => res.json())
        .then(data => {

            if (data.success) {

                if (pdf_name) {

                    addMessage(
                        `Switched to document: ${pdf_name}`,
                        "ai"
                    );

                } else {

                    addMessage(
                        "Switched to Search Across All PDFs mode.",
                        "ai"
                    );
                }
            }
        })
        .catch(err =>
            console.error(err)
        );
}

function deleteDocument(
    doc_id,
    pdf_name,
    event
) {

    event.stopPropagation();

    if (
        !confirm(
            `Are you sure you want to delete ${pdf_name}? This cannot be undone.`
        )
    ) {
        return;
    }

    fetch(
        `/user/documents/${doc_id}`,
        {
            method: "DELETE"
        }
    )
        .then(res => res.json())
        .then(data => {

            if (data.success) {

                addMessage(
                    `Document ${pdf_name} deleted successfully.`,
                    "ai"
                );

                fetchUserDocuments();

                setActiveDocument(null);

            } else {

                alert(
                    data.message ||
                    "Delete failed."
                );
            }
        })
        .catch(err =>
            console.error(err)
        );
}

// ==============================
// SEND MESSAGE
// ==============================

function sendMessage() {

    const message =
        input.value.trim();

    if (message === "") {
        return;
    }


    const welcome =
        document.querySelector(
            ".welcome-screen"
        );

    if (welcome) {
        welcome.remove();
    }

    addMessage(
        message,
        "user"
    );

    input.value = "";

    showTyping();

    fetch(
        "/api/chat",
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify({
                message: message,
                session_id:
                    currentSessionId
            })
        }
    )
        .then(response =>
            response.json()
        )
        .then(data => {

            removeTyping();

            const reply =
                data.reply ||
                data.response ||
                "I couldn't generate an answer.";

            addMessage(
                reply,
                "ai",
                data.source_used
            );

            // Automatically speak if inside Android APK
            if (window.RenvoraTTS) {
                speakMessage(reply, null);
            }

            if (
                data.session_id &&
                currentSessionId === null
            ) {

                currentSessionId =
                    data.session_id;

                const shareBtn =
                    document.getElementById(
                        "shareChatBtn"
                    );

                if (shareBtn) {
                    shareBtn.style.display =
                        "block";
                }

                fetchChatSessions();
            }
        })
        .catch(error => {

            removeTyping();

            addMessage(
                "Something went wrong. Please try again.",
                "ai"
            );

            console.error(error);
        });
}

// ==============================
// ADD MESSAGE
// ==============================

function addMessage(
    text,
    sender,
    source = null
) {

    const message =
        document.createElement(
            "div"
        );

    message.className =
        `message ${sender}`;

    const bubble =
        document.createElement(
            "div"
        );

    bubble.className =
        "message-content";

    bubble.textContent =
        text;

    if (
        sender === "ai" &&
        source &&
        source !== "None"
    ) {

        const sourceBadge =
            document.createElement(
                "div"
            );

        sourceBadge.style =
            "font-size: 0.75rem; color: #a1a1aa; margin-top: 5px;";

        sourceBadge.innerHTML =
            `<i class="bi bi-info-circle"></i> Source: ${escapeHtml(source)}`;

        bubble.appendChild(
            sourceBadge
        );
    }

    message.appendChild(
        bubble
    );

    if (sender === "ai") {

        const actionDiv =
            document.createElement(
                "div"
            );

        actionDiv.className =
            "message-actions";

        const listenBtn =
            document.createElement(
                "button"
            );

        listenBtn.className =
            "listen-btn";

        listenBtn.innerHTML =
            "🔊 Listen";

        listenBtn.onclick =
            () => {
                speakMessage(
                    text,
                    listenBtn
                );
            };

        actionDiv.appendChild(
            listenBtn
        );

        message.appendChild(
            actionDiv
        );
    }

    chatBody.appendChild(
        message
    );

    chatBody.scrollTop =
        chatBody.scrollHeight;
}

// ==============================
// AI TYPING
// ==============================

function showTyping() {

    const oldTyping =
        document.getElementById(
            "typing"
        );

    if (oldTyping) {
        oldTyping.remove();
    }

    const typing =
        document.createElement(
            "div"
        );

    typing.className =
        "message ai typing";

    typing.id =
        "typing";

    typing.innerHTML = `
        <div class="message-content">
            Thinking...
        </div>
    `;

    chatBody.appendChild(
        typing
    );

    chatBody.scrollTop =
        chatBody.scrollHeight;
}

function removeTyping() {

    const typing =
        document.getElementById(
            "typing"
        );

    if (typing) {
        typing.remove();
    }
}

// ==============================
// NEW CHAT
// ==============================

function startNewChat() {

    stopVoiceEverything();

    currentSessionId = null;

    document
        .querySelectorAll(
            "#sessionList .chat-item"
        )
        .forEach(item =>
            item.classList.remove(
                "active"
            )
        );

    const shareBtn =
        document.getElementById(
            "shareChatBtn"
        );

    if (shareBtn) {
        shareBtn.style.display =
            "none";
    }

    chatBody.innerHTML = `
        <div class="welcome-screen">
            <h1>Hello 👋</h1>
            <p>How can I help you today?</p>
        </div>
    `;
}

if (newChatBtn) {
    newChatBtn.addEventListener(
        "click",
        startNewChat
    );
}

// ==============================
// SEARCH
// ==============================

const searchInput =
    document.getElementById(
        "chatSearchInput"
    );

if (searchInput) {

    searchInput.addEventListener(
        "input",
        function (e) {

            const term =
                e.target.value
                    .toLowerCase();

            document
                .querySelectorAll(
                    "#sessionList .chat-item"
                )
                .forEach(item => {

                    const name =
                        item
                            .querySelector(
                                ".doc-name"
                            );

                    const text =
                        name
                            ? name.innerText
                                .toLowerCase()
                            : "";

                    item.style.display =
                        text.includes(term)
                            ? "flex"
                            : "none";
                });

            document
                .querySelectorAll(
                    "#documentList .chat-item:not(#searchAllDoc)"
                )
                .forEach(item => {

                    const name =
                        item
                            .querySelector(
                                ".doc-name"
                            );

                    const text =
                        name
                            ? name.innerText
                                .toLowerCase()
                            : "";

                    item.style.display =
                        text.includes(term)
                            ? "flex"
                            : "none";
                });
        }
    );
}

// ==============================
// SHARE CHAT
// ==============================

const shareChatBtn =
    document.getElementById(
        "shareChatBtn"
    );

if (shareChatBtn) {

    shareChatBtn.addEventListener(
        "click",
        () => {

            if (!currentSessionId) {
                return;
            }

            let transcript = "";

            document
                .querySelectorAll(
                    ".message"
                )
                .forEach(msg => {

                    const isUser =
                        msg.classList.contains(
                            "user"
                        );

                    const content =
                        msg.querySelector(
                            ".message-content"
                        );

                    if (!content) {
                        return;
                    }

                    const text =
                        content.innerText.replace(
                            /Source:.*$/g,
                            ""
                        );

                    transcript +=
                        (
                            isUser
                                ? "User: "
                                : "AI: "
                        ) +
                        text +
                        "\n\n";
                });

            navigator.clipboard
                .writeText(
                    transcript
                )
                .then(() => {
                    alert(
                        "Chat transcript copied to clipboard!"
                    );
                })
                .catch(() => {
                    alert(
                        "Unable to copy transcript."
                    );
                });
        }
    );
}

// ==============================
// EVENTS
// ==============================

if (sendBtn) {
    sendBtn.addEventListener(
        "click",
        sendMessage
    );
}

if (input) {
    input.addEventListener(
        "keypress",
        function (e) {

            if (e.key === "Enter") {
                sendMessage();
            }
        }
    );
}

// =============================================================
// EXISTING AI MESSAGE LISTEN BUTTON
// =============================================================

function speakMessage(
    text,
    button
) {

    if (
        !("speechSynthesis" in window)
    ) {
        return;
    }

    stopVoiceSpeaking();

    const cleanText =
        cleanSpeechText(text);

    const speech =
        new SpeechSynthesisUtterance(
            cleanText
        );

    speech.lang =
        selectedVoiceLanguage;

    speech.rate = 0.82;
    speech.pitch = 1;
    speech.volume = 1;

    const voice =
        findBestBrowserVoice(
            window.speechSynthesis.getVoices(),
            selectedVoiceLanguage
        );

    if (voice) {
        speech.voice = voice;
    }

    if (button) {
        button.innerHTML =
            "⏸ Speaking...";
    }

    voiceSpeaking = true;

    speech.onend = () => {

        voiceSpeaking = false;

        if (button) {
            button.innerHTML =
                "🔊 Listen";
        }
    };

    speech.onerror = () => {

        voiceSpeaking = false;

        if (button) {
            button.innerHTML =
                "🔊 Listen";
        }
    };

    if (window.RenvoraTTS) {
        window.RenvoraTTS.postMessage(speech.text);
    } else {
        window.speechSynthesis.speak(speech);
    }
}

// =============================================================
// INLINE CHAT VOICE
// =============================================================

function initInlineVoice() {

    if (
        !chatVoiceBtn ||
        !voiceMode
    ) {
        console.log(
            "[Voice] Inline voice UI not found."
        );

        return;
    }

    const Recognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!Recognition) {

        chatVoiceBtn.disabled = true;

        chatVoiceBtn.title =
            "Voice recognition is not supported in this browser.";

        return;
    }

    voiceRecognition =
        new Recognition();

    voiceRecognition.continuous =
        false;

    voiceRecognition.interimResults =
        true;

    voiceRecognition.maxAlternatives =
        1;

    voiceRecognition.lang =
        selectedVoiceLanguage;

    // ---------------------------------------------------------
    // OPEN VOICE MODE
    // ---------------------------------------------------------

    chatVoiceBtn.addEventListener(
        "click",
        function (event) {

            event.preventDefault();

            openVoiceMode();
        }
    );

    // ---------------------------------------------------------
    // CLOSE VOICE MODE
    // ---------------------------------------------------------

    if (voiceCloseBtn) {

        voiceCloseBtn.addEventListener(
            "click",
            function () {

                closeVoiceMode();
            }
        );
    }

    // ---------------------------------------------------------
    // STOP
    // ---------------------------------------------------------

    if (voiceStopBtn) {

        voiceStopBtn.addEventListener(
            "click",
            function () {

                stopVoiceEverything();

                if (voiceMode) {
                    voiceMode.classList.remove(
                        "listening"
                    );

                    voiceMode.classList.remove(
                        "speaking"
                    );
                }

                setVoiceReady();
            }
        );
    }

    // ---------------------------------------------------------
    // RECOGNITION START
    // ---------------------------------------------------------

    voiceRecognition.onstart =
        function () {

            voiceListening = true;

            if (voiceMode) {
                voiceMode.classList.add(
                    "listening"
                );

                voiceMode.classList.remove(
                    "speaking"
                );
            }

            if (chatVoiceStatus) {
                chatVoiceStatus.textContent =
                    "Listening...";
            }

            if (chatVoiceHint) {
                chatVoiceHint.textContent =
                    "Speak naturally";
            }
        };

    // ---------------------------------------------------------
    // RESULT
    // ---------------------------------------------------------

    voiceRecognition.onresult =
        function (event) {

            let finalText = "";
            let interimText = "";

            for (
                let i = event.resultIndex;
                i < event.results.length;
                i++
            ) {

                const transcript =
                    event.results[i][0]
                        .transcript;

                if (
                    event.results[i].isFinal
                ) {
                    finalText += transcript;
                } else {
                    interimText += transcript;
                }
            }

            const visibleText =
                (
                    finalText ||
                    interimText ||
                    ""
                ).trim();

            if (
                visibleText &&
                chatVoiceHint
            ) {

                chatVoiceHint.textContent =
                    visibleText;
            }

            if (
                finalText.trim()
            ) {

                handleVoiceQuestion(
                    finalText.trim()
                );
            }
        };

    // ---------------------------------------------------------
    // END
    // ---------------------------------------------------------

    voiceRecognition.onend =
        function () {

            voiceListening = false;

            if (voiceMode) {

                voiceMode.classList.remove(
                    "listening"
                );
            }

            if (
                !voiceProcessing &&
                !voiceSpeaking
            ) {
                setVoiceReady();
            }
        };

    // ---------------------------------------------------------
    // ERROR
    // ---------------------------------------------------------

    voiceRecognition.onerror =
        function (event) {

            console.error(
                "[Voice] Recognition error:",
                event.error
            );

            voiceListening =
                false;

            voiceProcessing =
                false;

            if (voiceMode) {
                voiceMode.classList.remove(
                    "listening"
                );
            }

            if (
                event.error ===
                "not-allowed"
            ) {

                if (chatVoiceStatus) {
                    chatVoiceStatus.textContent =
                        "Microphone blocked";
                }

                if (chatVoiceHint) {
                    chatVoiceHint.textContent =
                        "Allow microphone permission in the browser.";
                }

                return;
            }

            if (
                event.error ===
                "no-speech"
            ) {

                if (chatVoiceStatus) {
                    chatVoiceStatus.textContent =
                        "No speech detected";
                }

                if (chatVoiceHint) {
                    chatVoiceHint.textContent =
                        "Please speak and try again.";
                }

                setTimeout(
                    setVoiceReady,
                    1200
                );

                return;
            }

            if (
                chatVoiceStatus
            ) {
                chatVoiceStatus.textContent =
                    "Voice error";
            }

            if (
                chatVoiceHint
            ) {
                chatVoiceHint.textContent =
                    "Please try again.";
            }
        };

    // ---------------------------------------------------------
    // OPEN AND START
    // ---------------------------------------------------------

    function openVoiceMode() {

        if (voiceProcessing) {
            return;
        }

        stopVoiceSpeaking();

        if (voiceMode) {

            voiceMode.classList.add(
                "active"
            );

            voiceMode.setAttribute(
                "aria-hidden",
                "false"
            );
        }

        if (input) {
            input.blur();
        }

        startVoiceListening();
    }

    // ---------------------------------------------------------
    // CLOSE
    // ---------------------------------------------------------

    function closeVoiceMode() {

        stopVoiceEverything();

        if (voiceMode) {

            voiceMode.classList.remove(
                "active"
            );

            voiceMode.classList.remove(
                "listening"
            );

            voiceMode.classList.remove(
                "speaking"
            );

            voiceMode.setAttribute(
                "aria-hidden",
                "true"
            );
        }

        setVoiceReady();
    }

    // ---------------------------------------------------------
    // START RECOGNITION
    // ---------------------------------------------------------

    function startVoiceListening() {

        if (
            !voiceRecognition ||
            voiceListening ||
            voiceProcessing
        ) {
            return;
        }

        voiceRecognition.lang =
            selectedVoiceLanguage;

        try {

            voiceRecognition.start();

        } catch (error) {

            console.warn(
                "[Voice] Recognition start:",
                error
            );
        }
    }

    // ---------------------------------------------------------
    // HANDLE VOICE QUESTION
    // ---------------------------------------------------------

    async function handleVoiceQuestion(
        question
    ) {

        if (!question) {
            return;
        }

        stopVoiceSpeaking();

        voiceListening =
            false;

        voiceProcessing =
            true;

        if (voiceMode) {
            voiceMode.classList.remove(
                "listening"
            );
        }

        // -----------------------------------------------------
        // IMPORTANT:
        // Put recognized speech into normal chat input.
        // -----------------------------------------------------

        if (input) {
            input.value =
                question;
        }

        // -----------------------------------------------------
        // Remove welcome screen
        // -----------------------------------------------------

        const welcome =
            document.querySelector(
                ".welcome-screen"
            );

        if (welcome) {
            welcome.remove();
        }

        // -----------------------------------------------------
        // Add user message automatically
        // -----------------------------------------------------

        addMessage(
            question,
            "user"
        );

        // Clear input after adding message
        if (input) {
            input.value = "";
        }

        // Show normal chat thinking message too
        showTyping();

        updateVoiceStatus(
            "Thinking...",
            question
        );

        try {

            const response =
                await fetch(
                    "/api/chat",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        credentials:
                            "same-origin",

                        // IMPORTANT:
                        // Same backend API.
                        // No backend changes.
                        body: JSON.stringify({
                            message:
                                question,

                            session_id:
                                currentSessionId
                        })
                    }
                );

            let data;

            try {
                data =
                    await response.json();
            } catch (error) {
                throw new Error(
                    "Invalid server response."
                );
            }

            removeTyping();

            if (
                !response.ok ||
                data.success === false
            ) {

                throw new Error(
                    data.reply ||
                    data.message ||
                    "Unable to get AI response."
                );
            }

            const answer =
                (
                    data.reply ||
                    data.response ||
                    ""
                ).trim();

            if (!answer) {

                throw new Error(
                    "Renvora returned an empty answer."
                );
            }

            // -------------------------------------------------
            // DISPLAY AI TEXT IN CHAT
            // -------------------------------------------------

            addMessage(
                answer,
                "ai",
                data.source_used
            );

            if (
                data.session_id &&
                currentSessionId === null
            ) {

                currentSessionId =
                    data.session_id;

                const shareBtn =
                    document.getElementById(
                        "shareChatBtn"
                    );

                if (shareBtn) {
                    shareBtn.style.display =
                        "block";
                }

                fetchChatSessions();
            }

            // -------------------------------------------------
            // SPEAK SAME ANSWER
            // -------------------------------------------------

            voiceProcessing =
                false;

            speakInlineAnswer(
                answer
            );

        } catch (error) {

            removeTyping();

            voiceProcessing =
                false;

            console.error(
                "[Voice] Chat error:",
                error
            );

            addMessage(
                "Something went wrong. Please try again.",
                "ai"
            );

            updateVoiceStatus(
                "Something went wrong",
                error.message ||
                "Unable to connect to Renvora AI."
            );

            setTimeout(
                setVoiceReady,
                2000
            );
        }
    }

    // ---------------------------------------------------------
    // SPEAK INLINE ANSWER
    // ---------------------------------------------------------

    function speakInlineAnswer(
        text
    ) {

        if (
            !("speechSynthesis" in window)
        ) {

            voiceSpeaking =
                false;

            setVoiceReady();

            return;
        }

        stopVoiceSpeaking();

        speechQueue =
            splitSpeechIntoSentences(
                text
            );

        speechIndex =
            0;

        if (
            speechQueue.length ===
            0
        ) {

            setVoiceReady();

            return;
        }

        speakNextInlineSentence();
    }

    // ---------------------------------------------------------
    // NEXT SENTENCE
    // ---------------------------------------------------------

    function speakNextInlineSentence() {

        if (
            speechIndex >=
            speechQueue.length
        ) {

            voiceSpeaking =
                false;

            if (voiceMode) {

                voiceMode.classList.remove(
                    "speaking"
                );

                voiceMode.classList.remove(
                    "listening"
                );
            }

            updateVoiceStatus(
                "Ready for your next question",
                "Tap the microphone to speak again"
            );

            // Automatically listen again
            setTimeout(
                function () {

                    if (
                        voiceMode &&
                        voiceMode.classList.contains(
                            "active"
                        )
                    ) {
                        startVoiceListening();
                    }

                },
                600
            );

            return;
        }

        const sentence =
            speechQueue[
                speechIndex
            ];

        const speech =
            new SpeechSynthesisUtterance(
                sentence
            );

        speech.lang =
            selectedVoiceLanguage;

        // Current clean/slower voice
        speech.rate =
            0.82;

        speech.pitch =
            1;

        speech.volume =
            1;

        const voice =
            findBestBrowserVoice(
                window.speechSynthesis
                    .getVoices(),
                selectedVoiceLanguage
            );

        if (voice) {
            speech.voice =
                voice;
        }

        speech.onstart =
            function () {

                voiceSpeaking =
                    true;

                if (voiceMode) {

                    voiceMode.classList.remove(
                        "listening"
                    );

                    voiceMode.classList.add(
                        "speaking"
                    );
                }

                updateVoiceStatus(
                    "Renvora is speaking...",
                    sentence
                );
            };

        speech.onend =
            function () {

                if (!voiceSpeaking) {
                    return;
                }

                speechIndex++;

                setTimeout(
                    speakNextInlineSentence,
                    220
                );
            };

        speech.onerror =
            function (event) {

                console.error(
                    "[Voice] TTS error:",
                    event
                );

                voiceSpeaking =
                    false;

                setVoiceReady();
            };

        if (window.RenvoraTTS) {
            window.RenvoraTTS.postMessage(speech.text);
        } else {
            window.speechSynthesis.speak(speech);
        }
    }

    // ---------------------------------------------------------
    // CLEAN SPEECH
    // ---------------------------------------------------------

    function cleanSpeechText(
        text
    ) {

        let cleaned =
            String(text || "");

        cleaned =
            cleaned.replace(
                /https?:\/\/\S+/gi,
                ""
            );

        cleaned =
            cleaned.replace(
                /[*_`#~]/g,
                ""
            );

        cleaned =
            cleaned.replace(
                /^[\s]*[-•▪◦]\s+/gm,
                ""
            );

        cleaned =
            cleaned.replace(
                /\r?\n+/g,
                ". "
            );

        cleaned =
            cleaned.replace(
                /[\[\]\{\}]/g,
                ""
            );

        cleaned =
            cleaned.replace(
                /([.!?।])\1+/g,
                "$1"
            );

        cleaned =
            cleaned.replace(
                /\s+/g,
                " "
            );

        return cleaned.trim();
    }

    // ---------------------------------------------------------
    // SENTENCE SPLITTER
    // ---------------------------------------------------------

    function splitSpeechIntoSentences(
        text
    ) {

        const clean =
            cleanSpeechText(
                text
            );

        if (!clean) {
            return [];
        }

        return clean
            .split(
                /(?<=[.!?।])\s+/
            )
            .map(
                sentence =>
                    sentence.trim()
            )
            .filter(
                sentence =>
                    sentence.length > 0
            );
    }

    // ---------------------------------------------------------
    // STOP SPEAKING
    // ---------------------------------------------------------

    function stopVoiceSpeaking() {

        if (window.RenvoraTTS) {
            window.RenvoraTTS.postMessage("STOP");
        } else if (
            "speechSynthesis" in window
        ) {
            window.speechSynthesis.cancel();
        }

        speechQueue = [];
        speechIndex = 0;

        voiceSpeaking = false;

        if (voiceMode) {
            voiceMode.classList.remove(
                "speaking"
            );
        }
    }

    // ---------------------------------------------------------
    // STOP EVERYTHING
    // ---------------------------------------------------------

    function stopVoiceEverything() {

        stopVoiceSpeaking();

        voiceProcessing =
            false;

        if (
            voiceRecognition &&
            voiceListening
        ) {

            try {
                voiceRecognition.stop();
            } catch (error) {
                console.warn(error);
            }
        }

        voiceListening =
            false;

        if (voiceMode) {

            voiceMode.classList.remove(
                "listening"
            );

            voiceMode.classList.remove(
                "speaking"
            );
        }
    }

    // ---------------------------------------------------------
    // VOICE READY
    // ---------------------------------------------------------

    function setVoiceReady() {

        voiceListening =
            false;

        voiceProcessing =
            false;

        if (voiceMode) {

            voiceMode.classList.remove(
                "listening"
            );

            voiceMode.classList.remove(
                "speaking"
            );
        }

        updateVoiceStatus(
            "Ready to talk",
            "Tap the microphone to start"
        );
    }

    // ---------------------------------------------------------
    // UPDATE VOICE STATUS
    // ---------------------------------------------------------

    function updateVoiceStatus(
        status,
        hint
    ) {

        if (chatVoiceStatus) {
            chatVoiceStatus.textContent =
                status;
        }

        if (chatVoiceHint) {
            chatVoiceHint.textContent =
                hint || "";
        }
    }
}

// =============================================================
// BROWSER VOICE HELPERS
// =============================================================

function findBestBrowserVoice(
    voices,
    language
) {

    if (
        !voices ||
        voices.length === 0
    ) {
        return null;
    }

    // Exact language first
    const exact =
        voices.find(
            voice =>
                voice.lang &&
                voice.lang.toLowerCase() ===
                language.toLowerCase()
        );

    if (exact) {
        return exact;
    }

    // Google voice for same language
    const base =
        language
            .split("-")[0]
            .toLowerCase();

    const googleVoice =
        voices.find(
            voice =>
                voice.name &&
                voice.name
                    .toLowerCase()
                    .includes("google") &&
                voice.lang &&
                voice.lang
                    .toLowerCase()
                    .startsWith(base)
        );

    if (googleVoice) {
        return googleVoice;
    }

    // Same language
    const sameLanguage =
        voices.find(
            voice =>
                voice.lang &&
                voice.lang
                    .toLowerCase()
                    .startsWith(base)
        );

    if (sameLanguage) {
        return sameLanguage;
    }

    return voices[0] || null;
}

function escapeHtml(
    value
) {

    return String(value || "")
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );
}


// =============================================================
// LOAD BROWSER VOICES
// =============================================================

if (
    "speechSynthesis" in window
) {

    window.speechSynthesis.onvoiceschanged =
        function () {

            const voices =
                window.speechSynthesis
                    .getVoices();

            console.log(
                "[Voice] Available voices:",
                voices.length
            );
        };
}
// ===============================
// MOBILE SIDEBAR MENU
// ===============================

document.addEventListener("DOMContentLoaded", function () {

    const mobileMenuBtn = document.getElementById("mobileMenuBtn");
    const sidebar = document.getElementById("sidebar");
    const sidebarOverlay = document.getElementById("sidebarOverlay");

    if (!mobileMenuBtn || !sidebar) {
        console.warn("Mobile menu elements not found");
        return;
    }

    // Note: The open/close and overlay click handlers are intentionally omitted here 
    // because they are already handled by inline onclick handlers in chat.html.
    // Close sidebar when a sidebar link/item is clicked on mobile
    sidebar.addEventListener("click", function (e) {

        if (window.innerWidth <= 768) {

            const target = e.target.closest("a, .chat-item");

            if (target && !target.classList.contains("new-chat-btn")) {
                sidebar.classList.remove("active");

                if (sidebarOverlay) {
                    sidebarOverlay.classList.remove("active");
                }
            }
        }

    });

});
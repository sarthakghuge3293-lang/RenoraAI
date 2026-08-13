(function () {
    "use strict";

    const voiceButton =
        document.getElementById("chatVoiceBtn");

    const voicePanel =
        document.getElementById("chatInlineVoice");

    const closeButton =
        document.getElementById("closeChatVoice");

    const statusElement =
        document.getElementById("chatVoiceStatus");

    const hintElement =
        document.getElementById("chatVoiceHint");

    const input =
        document.getElementById("messageInput");

    const chatBody =
        document.getElementById("chatBody");

    if (
        !voiceButton ||
        !voicePanel ||
        !closeButton ||
        !statusElement ||
        !hintElement ||
        !input ||
        !chatBody
    ) {
        console.error(
            "[Inline Voice] Required elements not found."
        );

        return;
    }

    // ========================================================
    // STATE
    // ========================================================

    let recognition = null;

    let listening = false;
    let processing = false;
    let speaking = false;

    let selectedLanguage = "en-IN";

    let queue = [];
    let queueIndex = 0;

    // ========================================================
    // SPEECH RECOGNITION
    // ========================================================

    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {

        voiceButton.disabled = true;

        voiceButton.title =
            "Voice recognition is not supported.";

        return;
    }

    recognition =
        new SpeechRecognition();

    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.lang =
        selectedLanguage;

    // ========================================================
    // OPEN
    // ========================================================

    voiceButton.addEventListener(
        "click",
        function () {

            if (
                listening ||
                processing
            ) {
                return;
            }

            stopSpeaking();

            voicePanel.classList.add(
                "active"
            );

            startListening();
        }
    );

    // ========================================================
    // CLOSE
    // ========================================================

    closeButton.addEventListener(
        "click",
        function () {

            stopAll();

            voicePanel.classList.remove(
                "active"
            );

            statusElement.textContent =
                "Ready to talk";

            hintElement.textContent =
                "Tap the microphone to speak";
        }
    );

    // ========================================================
    // START LISTENING
    // ========================================================

    function startListening() {

        if (
            !recognition ||
            listening ||
            processing
        ) {
            return;
        }

        recognition.lang =
            selectedLanguage;

        try {

            recognition.start();

        } catch (error) {

            console.warn(
                "[Inline Voice] Start:",
                error
            );
        }
    }

    // ========================================================
    // RECOGNITION START
    // ========================================================

    recognition.onstart =
        function () {

            listening = true;

            voicePanel.classList.add(
                "listening"
            );

            voicePanel.classList.remove(
                "speaking"
            );

            statusElement.textContent =
                "Listening...";

            hintElement.textContent =
                "Speak naturally";
        };

    // ========================================================
    // RESULT
    // ========================================================

    recognition.onresult =
        function (event) {

            let finalText = "";
            let interimText = "";

            for (
                let i = event.resultIndex;
                i < event.results.length;
                i++
            ) {

                const text =
                    event.results[i][0]
                        .transcript;

                if (
                    event.results[i].isFinal
                ) {

                    finalText += text;

                } else {

                    interimText += text;
                }
            }

            const visibleText =
                (
                    finalText ||
                    interimText ||
                    ""
                ).trim();

            if (visibleText) {

                hintElement.textContent =
                    visibleText;
            }

            if (
                finalText.trim()
            ) {

                sendVoiceQuestion(
                    finalText.trim()
                );
            }
        };

    // ========================================================
    // END
    // ========================================================

    recognition.onend =
        function () {

            listening = false;

            voicePanel.classList.remove(
                "listening"
            );

            if (
                !processing &&
                !speaking
            ) {

                statusElement.textContent =
                    "Ready to talk";

                hintElement.textContent =
                    "Tap the microphone to speak";
            }
        };

    // ========================================================
    // ERROR
    // ========================================================

    recognition.onerror =
        function (event) {

            console.error(
                "[Inline Voice] Recognition:",
                event.error
            );

            listening = false;
            processing = false;

            voicePanel.classList.remove(
                "listening"
            );

            if (
                event.error ===
                "not-allowed"
            ) {

                statusElement.textContent =
                    "Microphone blocked";

                hintElement.textContent =
                    "Allow microphone access in Chrome.";

                return;
            }

            if (
                event.error ===
                "no-speech"
            ) {

                statusElement.textContent =
                    "No speech detected";

                hintElement.textContent =
                    "Please speak again.";

                return;
            }

            statusElement.textContent =
                "Voice error";

            hintElement.textContent =
                "Please try again.";
        };

    // ========================================================
    // SEND VOICE QUESTION
    // ========================================================

    async function sendVoiceQuestion(
        question
    ) {

        if (!question) {
            return;
        }

        listening = false;
        processing = true;

        voicePanel.classList.remove(
            "listening"
        );

        // Put speech into normal input briefly
        input.value =
            question;

        // Remove welcome
        const welcome =
            document.querySelector(
                ".welcome-screen"
            );

        if (welcome) {
            welcome.remove();
        }

        // Add user message to chat
        if (
            typeof window.addMessage ===
            "function"
        ) {

            window.addMessage(
                question,
                "user"
            );

        } else {

            addFallbackMessage(
                question,
                "user"
            );
        }

        input.value = "";

        // Show existing typing UI
        if (
            typeof window.showTyping ===
            "function"
        ) {
            window.showTyping();
        }

        statusElement.textContent =
            "Thinking...";

        hintElement.textContent =
            question;

        try {

            /*
             * SAME EXISTING BACKEND.
             * No backend modifications.
             */

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
                                window.currentSessionId ||
                                null
                        })
                    }
                );

            const data =
                await response.json();

            if (
                typeof window.removeTyping ===
                "function"
            ) {
                window.removeTyping();
            }

            if (
                !response.ok ||
                data.success === false
            ) {

                throw new Error(
                    data.reply ||
                    data.message ||
                    "AI response failed."
                );
            }

            const answer =
                String(
                    data.reply ||
                    data.response ||
                    ""
                ).trim();

            if (!answer) {

                throw new Error(
                    "AI returned an empty answer."
                );
            }

            // Show AI answer in text
            if (
                typeof window.addMessage ===
                "function"
            ) {

                window.addMessage(
                    answer,
                    "ai",
                    data.source_used
                );

            } else {

                addFallbackMessage(
                    answer,
                    "ai"
                );
            }

            // Keep session when possible
            if (
                data.session_id &&
                typeof window.currentSessionId !==
                "undefined"
            ) {

                window.currentSessionId =
                    data.session_id;
            }

            processing = false;

            // Read AI answer
            speakAnswer(answer);

        } catch (error) {

            if (
                typeof window.removeTyping ===
                "function"
            ) {
                window.removeTyping();
            }

            processing = false;

            console.error(
                "[Inline Voice] Chat error:",
                error
            );

            if (
                typeof window.addMessage ===
                "function"
            ) {

                window.addMessage(
                    "Something went wrong. Please try again.",
                    "ai"
                );

            } else {

                addFallbackMessage(
                    "Something went wrong. Please try again.",
                    "ai"
                );
            }

            statusElement.textContent =
                "Something went wrong";

            hintElement.textContent =
                error.message;
        }
    }

    // ========================================================
    // SPEAK ANSWER
    // ========================================================

    function speakAnswer(
        text
    ) {

        if (
            !("speechSynthesis" in window)
        ) {

            statusElement.textContent =
                "Answer ready";

            hintElement.textContent =
                text;

            return;
        }

        stopSpeaking();

        queue =
            splitSentences(
                cleanText(text)
            );

        queueIndex = 0;

        if (!queue.length) {
            return;
        }

        speakNext();
    }

    // ========================================================
    // SPEAK NEXT SENTENCE
    // ========================================================

    function speakNext() {

        if (
            queueIndex >=
            queue.length
        ) {

            speaking = false;

            voicePanel.classList.remove(
                "speaking"
            );

            statusElement.textContent =
                "Ready to talk";

            hintElement.textContent =
                "Tap the microphone to speak";

            // Automatically listen again
            if (
                voicePanel.classList.contains(
                    "active"
                )
            ) {

                setTimeout(
                    startListening,
                    600
                );
            }

            return;
        }

        const sentence =
            queue[queueIndex];

        const speech =
            new SpeechSynthesisUtterance(
                sentence
            );

        speech.lang =
            selectedLanguage;

        // Slow and clear
        speech.rate =
            0.82;

        speech.pitch =
            1;

        speech.volume =
            1;

        const browserVoice =
            findVoice(
                window.speechSynthesis
                    .getVoices(),
                selectedLanguage
            );

        if (browserVoice) {
            speech.voice =
                browserVoice;
        }

        speech.onstart =
            function () {

                speaking = true;

                voicePanel.classList.remove(
                    "listening"
                );

                voicePanel.classList.add(
                    "speaking"
                );

                statusElement.textContent =
                    "Renvora is speaking...";

                hintElement.textContent =
                    sentence;
            };

        speech.onend =
            function () {

                if (!speaking) {
                    return;
                }

                queueIndex++;

                setTimeout(
                    speakNext,
                    220
                );
            };

        speech.onerror =
            function () {

                speaking = false;

                voicePanel.classList.remove(
                    "speaking"
                );

                statusElement.textContent =
                    "Ready to talk";
            };

        window.speechSynthesis.speak(
            speech
        );
    }

    // ========================================================
    // CLEAN TEXT
    // ========================================================

    function cleanText(
        text
    ) {

        let value =
            String(text || "");

        value =
            value.replace(
                /https?:\/\/\S+/gi,
                ""
            );

        value =
            value.replace(
                /[*_`#~]/g,
                ""
            );

        value =
            value.replace(
                /^[\s]*[-•▪◦]\s+/gm,
                ""
            );

        value =
            value.replace(
                /\r?\n+/g,
                ". "
            );

        value =
            value.replace(
                /([.!?।])\1+/g,
                "$1"
            );

        value =
            value.replace(
                /\s+/g,
                " "
            );

        return value.trim();
    }

    // ========================================================
    // SPLIT SENTENCES
    // ========================================================

    function splitSentences(
        text
    ) {

        return text
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

    // ========================================================
    // STOP
    // ========================================================

    function stopSpeaking() {

        if (
            "speechSynthesis" in window
        ) {
            window.speechSynthesis.cancel();
        }

        queue = [];
        queueIndex = 0;
        speaking = false;

        voicePanel.classList.remove(
            "speaking"
        );
    }

    function stopAll() {

        stopSpeaking();

        if (
            recognition &&
            listening
        ) {

            try {
                recognition.stop();
            } catch (error) {}
        }

        listening = false;
        processing = false;

        voicePanel.classList.remove(
            "listening"
        );

        voicePanel.classList.remove(
            "speaking"
        );
    }

    // ========================================================
    // FIND BEST VOICE
    // ========================================================

    function findVoice(
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

        const base =
            language
                .split("-")[0]
                .toLowerCase();

        const google =
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

        if (google) {
            return google;
        }

        return (
            voices.find(
                voice =>
                    voice.lang &&
                    voice.lang
                        .toLowerCase()
                        .startsWith(base)
            ) ||
            voices[0] ||
            null
        );
    }

    // ========================================================
    // FALLBACK MESSAGE
    // ========================================================

    function addFallbackMessage(
        text,
        sender
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

        message.appendChild(
            bubble
        );

        chatBody.appendChild(
            message
        );

        chatBody.scrollTop =
            chatBody.scrollHeight;
    }

})();
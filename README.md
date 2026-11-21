# 🎓 AI College Assistant (UTU)

An intelligent, document-grounded academic assistant designed specifically for university students. It provides accurate answers regarding official B.Tech syllabus modules, credit schemes, and academic/holiday calendars through a modern chat interface or completely hands-free voice mode.

---

## ⚖️ Comparison: Basic RAG Chatbot vs. AI College Assistant

| Feature | 🤖 Standard / Basic RAG Chatbot | 🌟 AI College Assistant (This Project) |
| :--- | :--- | :--- |
| **Greeting & Intent Handling** | ❌ **Blind Retrieval:** Searches the database even for casual greetings like *"hi"* or *"what's my name?"*, resulting in irrelevant document chunks and fake source citations. | ✅ **Smart Intent Filter:** Intelligently recognizes greetings and student identity without pulling random document chunks. Only queries the database when academic information is needed. |
| **Voice Response Speed** | ⏳ **Slow (5–8 seconds):** Waits for the entire text response to be generated before converting it to audio, causing noticeable delay. | ⚡ **Sub-Second (<1s):** Starts speaking the first sentence within ~1 second using a live parallel streaming audio queue. |
| **Voice Interruption (Barge-in)** | ❌ **No Interruption:** You must listen until it finishes talking. Trying to stop it or asking a new question breaks the session or is ignored. | 🎙️ **Instant Barge-in:** Say *"Stop"*, *"रुको"*, *"बस"*, or ask a new question mid-sentence; playback halts immediately and switches to the new question. |
| **Acoustic Echo Rejection** | ❌ **Feedback Loop:** The microphone picks up the assistant's own voice from the speakers and types it back into the chat as an endless loop. | 🛡️ **Zero Echo Loop:** Built-in acoustic similarity filter prevents speaker output from re-entering the microphone. |
| **Academic Accuracy** | ⚠️ **Generic Matching:** Frequently confuses general engineering topics with specific state university regulations. | ✅ **100% Grounded:** Retrieves exact subject codes, semester credits, and circular dates from official university syllabus and calendar documents. |
| **User Interface & Themes** | ❌ **Single / Rigid UI:** Fixed layout with cluttered technical debug boxes and chunky form buttons. | 🎨 **Modern Multi-Theme UI:** 4 instant themes (Pastel Light, Grey Shining, Rosewood, Sunset Peach) with clean, minimal cards. |
| **Cloud Hosting & Memory** | 💸 **Resource-Heavy:** Requires multi-gigabyte models and costly GPU servers ($50–$100/mo) that crash on free-tier cloud. | 🚀 **Ultra-Lightweight:** Runs on lightweight FastEmbed ONNX (~75MB RAM) and cloud PostgreSQL, running smoothly on free cloud hosting without memory crashes. |

---

## 🎯 Key Differences Explained Simply

### 1. No Accidental Searches on Simple Greetings
* **Basic RAG:** When you say *"Hello"* or *"My name is Pankaj"*, a basic RAG bot converts that into vectors, searches your syllabus files, and returns random course chunks with a fake "Verified Source" badge.
* **This Project:** It understands normal conversation naturally. Document searching is triggered only when you ask an actual academic question about courses, credits, exams, or holidays.

### 2. Instant Voice Instead of Long Waiting Times
* **Basic RAG:** Generates the whole response in text first, then calls a text-to-speech API. The student waits 5 to 8 seconds in complete silence before hearing any audio.
* **This Project:** Uses sentence streaming. As soon as the first few words are generated, speech begins within 1 second while the rest of the answer streams in parallel.

### 3. Natural Voice Interruption (No Annoying Loops)
* **Basic RAG:** Cannot be interrupted while speaking. Worse, laptop microphones often pick up the speaker audio and loop it infinitely.
* **This Project:** You can interrupt anytime by saying *"Stop"*, *"रुको"*, or by asking your next question. The assistant immediately stops talking and listens to you.

### 4. Verified University Documents
* **Basic RAG:** Often trained on generic internet data, giving inaccurate or outdated information from other colleges.
* **This Project:** Grounded exclusively in official university syllabus PDFs and official academic calendars. If a detail is not in the official document, it will not guess or hallucinate.

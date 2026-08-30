import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  const sendMessage = async () => {
    if (!question.trim()) return;

    const userMessage = {
      role: "user",
      content: question,
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");

    const response = await fetch("https://katherin-ai.onrender.com/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question: question,
        history: messages,
      }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let answer = "";

    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      const chunk = decoder.decode(value);
      answer += chunk;

      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1].content = answer;
        return updated;
      });
    }
  };
  return (
    <div className="app">
      <header className="header">
        <div className="logo">
          <div className="logo-icon">K</div>

          <div>
            <h2>KatherinAI</h2>
            <span>AI Portfolio Assistant</span>
          </div>
        </div>
      </header>

      <main className="main">
        {messages.length === 0 && (
          <div className="welcome">
            <h1>Hi, I'm KatherinAI 👋</h1>
            <p>
              Ask me anything about Katherin's skills, projects, education or
              achievements.
            </p>
          </div>
        )}

        <div className="chat-box">
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.role}`}>
              <div className="message-content">
                <div className="message-name">
                  {message.role === "user" ? "You" : "KatherinAI"}
                </div>

                <div className="markdown">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
              </div>
            </div>
          ))}

          <div ref={chatEndRef} />
        </div>

        {loading && <div className="typing">KatherinAI is typing...</div>}

        <div className="input-container">
          <div className="input-area">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  sendMessage();
                }
              }}
              placeholder="Ask about Katherin..."
            />

            <button onClick={sendMessage}>Send</button>
          </div>
        </div>
      </main>

      <footer className="footer">Built with React, FastAPI & Groq</footer>
    </div>
  );
}

export default App;

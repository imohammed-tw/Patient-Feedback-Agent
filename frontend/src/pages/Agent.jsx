import {
  Cog6ToothIcon,
  PaperAirplaneIcon,
  UserIcon,
  CpuChipIcon,
  ArrowLeftOnRectangleIcon,
  UserCircleIcon,
  WrenchScrewdriverIcon
} from "@heroicons/react/24/outline";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
export default function AgentPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [socket, setSocket] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [showProfileTooltip, setShowProfileTooltip] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);


  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");

    ws.onopen = () => {
      console.log("WebSocket connection opened! 🎉");
      const user = JSON.parse(localStorage.getItem("user"));
      if (user?.nhsNumber) {
        ws.send(JSON.stringify({ type: "init", nhsNumber: user.nhsNumber }));
        console.log("✅ Sent NHS Number for context:", user.nhsNumber);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket Error:", error);
    };

    ws.onmessage = (event) => {
      setIsLoading(false);
      setMessages((prev) => [...prev, { sender: "bot", text: event.data }]);
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected ❌");
    };

    setSocket(ws);

    return () => ws.close();
  }, []);

  const sendMessage = () => {
    if (!input.trim() || !socket) return;
    setIsLoading(true);
    socket.send(JSON.stringify({ type: "message", content: input }));
    setMessages((prev) => [...prev, { sender: "user", text: input }]);
    setInput("");
  };

  const handleLogout = () => {
    localStorage.removeItem("user");
    localStorage.removeItem("token");
    window.location.href = "/";
  };

  const fetchNotifications = async () => {
    const user = JSON.parse(localStorage.getItem("user"));
    if (!user?.nhsNumber) return;
  
    try {
      const res = await fetch(`http://localhost:8000/notifications/${user.nhsNumber}`);
      const data = await res.json();
      setNotifications(data.notifications || []);
      setShowNotifications(!showNotifications);  // toggle popup
    } catch (err) {
      console.error("Error fetching notifications:", err);
    }
  };

  const markAllAsRead = async () => {
    const user = JSON.parse(localStorage.getItem("user"));
    if (!user?.nhsNumber) return;
  
    try {
      await fetch(`http://localhost:8000/notifications/mark-read/${user.nhsNumber}`, {
        method: "POST"
      });
  
      // Re-fetch updated notifications
      fetchNotifications();
    } catch (err) {
      console.error("Error marking notifications as read:", err);
    }
  };
  
  

  const handleNewChat = () => {
  // Logic to start a new chat goes here
  setMessages([]);
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "new_chat" }));
  }
  console.log("New chat initiated");
};

  


  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col">
      {/* Top Bar */}
      <div className="flex justify-between items-center border-b border-gray-700 px-6 py-4 sticky top-0 z-10 bg-gray-900">
        <div className="text-2xl font-bold">NHS Patient Agent</div>
        <div className="flex gap-4 relative">
          <div className="relative">
          <UserCircleIcon className="w-6 h-6 cursor-pointer hover:text-blue-400"
            onMouseEnter={() => setShowProfileTooltip(true)}
            onMouseLeave={() => setShowProfileTooltip(false)} />
            {showProfileTooltip && (
              <div className="absolute -bottom-8 right-1 bg-gray-800 text-xs px-2 py-1 rounded">
                Profile
              </div>
            )}
            </div>

            <div className="relative">
    <button onClick={fetchNotifications}>
      <span className="relative">
        <span className="absolute -top-2 -right-2 bg-red-600 text-white text-xs rounded-full px-1.5 py-0.5">
          {notifications.length}
        </span>
        <svg
          className="w-6 h-6 text-white hover:text-blue-400 cursor-pointer"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11c0-3.314-2.686-6-6-6S6 7.686 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
      </span>
    </button>

    {/* 🔔 Dropdown */}
    {showNotifications && (
      <div className="absolute right-0 top-8 w-80 bg-gray-800 rounded shadow-lg text-sm z-50 max-h-96 overflow-y-auto p-3 border border-gray-600">
        <h4 className="text-white font-semibold mb-2">Notifications</h4>
        <button
          onClick={markAllAsRead}
          className="text-xs text-blue-400 hover:underline"
        >
          Mark all as read
        </button>
        {notifications.length === 0 ? (
          <p className="text-gray-400">No notifications yet.</p>
        ) : (
          notifications.map((n, i) => (
            <div key={i} className="mb-3 p-2 bg-gray-700 rounded">
              <p className={`font-semibold ${n.type === 'rejected' ? 'text-red-400' : 'text-green-400'}`}>
                {n.type === "rejected" ? "❌ Rejected" : "✅ Acknowledged"}
              </p>
              <p className="text-gray-300 text-sm mt-1">{n.message}</p>
              {n.feedback?.comment && (
              <p className="text-gray-400 text-xs mt-1">💬 "{n.feedback.comment}"</p>
            )}
            
            {n.note && (
              <p className="text-red-300 text-xs mt-1 italic">📝 Note: {n.note}</p>
            )}
              <p className="text-gray-500 text-xs mt-1">
                {new Date(n.timestamp).toLocaleString()}
              </p>
            </div>
          ))
        )}
      </div>
      )}
  </div>

          <Cog6ToothIcon 
            className="w-6 h-6 cursor-pointer hover:text-blue-400"
            onClick={() => setShowDropdown(!showDropdown)}
          />
          {showDropdown && (
            <div className="absolute right-0 top-9 w-32 bg-gray-800 rounded-md shadow-lg py-1 z-10">
              <div className="px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 cursor-pointer flex items-center gap-2">
                <WrenchScrewdriverIcon className="w-4 h-4" />
                Customise
              </div>
              <hr className="border-gray-600 my-2" />
              <div 
                className="px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 cursor-pointer flex items-center gap-2"
                onClick={handleLogout}
              >
                <ArrowLeftOnRectangleIcon className="w-4 h-4" />
                Logout
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-1/5 border-r border-gray-700 p-4 text-sm h-[calc(100vh-73px)] overflow-hidden">
        {/* New Chat Button */}
  <button
    onClick={handleNewChat}
    className="w-full bg-gray-700 hover:bg-gray-500 mt-1 text-white py-2 px-4 rounded-md text-sm font-medium transition-colors"
  >
    New Chat
  </button>
  
          <div className="text-gray-300 font-medium mt-5">Chat History</div>
        </aside>

        {/* Chat Area */}
        <main className="flex-1 flex flex-col h-[calc(100vh-73px)] relative">
          {/* Scrollable Messages Area */}
          <div className="flex-1 overflow-y-auto pt-6 pb-24 px-6 space-y-4 custom-scrollbar"
          style={{
              scrollbarWidth: 'thin',
              scrollbarColor: '#4B5563 #1F2937',
            }}>
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex items-start gap-2 ${
                  msg.sender === "user" ? "justify-end" : ""
                }`}
              >
                {msg.sender === "bot" ? (
                  <>
                    <CpuChipIcon className="w-6 h-6 text-green-400 mt-3 flex-shrink-0" />
                    <div className="bg-gray-700 p-3 rounded-md max-w-[70%] prose prose-invert break-words">
                      <ReactMarkdown>{msg.text}</ReactMarkdown>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="bg-blue-500 p-3 rounded-md max-w-[70%] text-white break-words">
                      {msg.text}
                    </div>
                    <UserIcon className="w-6 h-6 text-blue-400 mt-3 flex-shrink-0" />
                  </>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="flex items-start gap-2">
                <CpuChipIcon className="w-6 h-6 text-green-400 mt-1 flex-shrink-0" />
                <div className="bg-gray-700 p-3 rounded-md max-w-[70%]">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"></div>
                    <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-44 pointer-events-none bg-gradient-to-t from-gray-900 to-transparent"></div>
          {/* Input Field */}
          <div className=" absolute bottom-0 left-0 right-0 p-4">
            <div className="flex items-center border border-gray-500 rounded-full px-4 py-2 bg-gray-800/60 backdrop-blur-md max-w-2xl mx-auto shadow-lg">
              <input
                type="text"
                placeholder="Type your message..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                className="flex-1 bg-transparent outline-none text-gray-300 placeholder-gray-400"
              />
              <PaperAirplaneIcon
                className="w-5 h-5 text-gray-400 cursor-pointer hover:text-blue-400 transform hover:rotate-45 transition-transform duration-300  ml-3"
                onClick={sendMessage}
              />
            </div>
          </div>
        </main>
      </div>
      <style jsx global>{`
        /* Custom scrollbar styling */
        .custom-scrollbar::-webkit-scrollbar {
          width: 8px;
        }
        
        .custom-scrollbar::-webkit-scrollbar-track {
          background-color: #1F2937;
          border-radius: 4px;
        }
        
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: #4B5563;
          border-radius: 4px;
        }
        
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background-color: #6B7280;
        }
      `}</style>
    </div>
  );
}

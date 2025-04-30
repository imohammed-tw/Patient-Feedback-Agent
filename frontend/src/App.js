import React from "react";
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Auth from './pages/Auth';
import AgentPage from "./pages/Agent";

function App() {
  return (
  // <div className="">
  //   <Chatbot />;
  //   </div>
  <Router>
      <Routes>
        <Route path="/" element={<Auth />} />
        <Route path="/agent" element={<AgentPage />} />
      </Routes>
    </Router>
  );
}

export default App;

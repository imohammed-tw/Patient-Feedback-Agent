import { useState } from "react";
import AuthForm from "../components/AuthForm";

export default function Auth() {
    const [isLogin, setIsLogin] = useState(true);

    return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      {/* Header */}
        <div className="pt-4 pl-6 text-2xl font-bold border-b border-gray-700 pb-4 text-white">NHS</div>

      {/* Form */}
        <div className="flex flex-1 items-center justify-center">
        <div className="bg-gray-800 p-8 rounded-2xl shadow-xl w-full max-w-sm">
            <div className="flex justify-center mb-6">
            <button
                className={`px-4 py-2 rounded-l-full font-semibold ${
                isLogin ? "bg-blue-500 text-white" : "bg-gray-200"
                }`}
                onClick={() => setIsLogin(true)}
            >
            Login
            </button>
            <button
                className={`px-4 py-2 rounded-r-full font-semibold ${
                !isLogin ? "bg-blue-500 text-white" : "bg-gray-200"
                }`}
                onClick={() => setIsLogin(false)}
            >
            Register
            </button>
            </div>
            <AuthForm isLogin={isLogin} />
        </div>
        </div>
    </div>
    );
}

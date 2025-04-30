import { useState } from "react";
import axios from "axios";
import toast from "react-hot-toast";
import { motion } from "framer-motion";
import { EyeIcon, EyeSlashIcon, InformationCircleIcon } from "@heroicons/react/24/outline";
import { useNavigate } from "react-router-dom";

export default function AuthForm({ isLogin }) {
  const [formData, setFormData] = useState({
    name: "",
    password: "",
    nhsNumber: "", // NHS Number instead of confirmPassword
  });

  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) =>
    setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    const url = isLogin
      ? "http://localhost:8000/login"
      : "http://localhost:8000/register";

    const payload = isLogin
      ? {
      nhsNumber: formData.nhsNumber,
      password: formData.password,
    }
      : {
          name: formData.name,
          password: formData.password,
          nhsNumber: formData.nhsNumber,
        };

    try {
      const res = await axios.post(url, payload);
      toast.success(`${isLogin ? "Logged in" : "Registered"} successfully!`);
      console.log("Response:", res.data);
      if (isLogin) {
      // Save user info to localStorage
        localStorage.setItem("user", JSON.stringify(res.data.user));
        navigate("/agent"); // 🔁 Redirect to agent dashboard
      }
    } catch (err) {
      console.error("Error:", err);
      toast.error(err?.response?.data?.message || "Something went wrong!");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
  <motion.form
    onSubmit={handleSubmit}
    className="space-y-5"
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 1.5 }}
  >
    {/* Name - only for register */}
    {!isLogin && (
      <input
        type="text"
        name="name"
        placeholder="Name"
        value={formData.name}
        onChange={handleChange}
        required
        className="w-full px-4 bg-gray-800 py-2 rounded border focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
    )}

    {/* NHS Number - always required */}
    <div className="relative">
      <input
        type="text"
        name="nhsNumber"
        placeholder="NHS Number"
        value={formData.nhsNumber}
        onChange={handleChange}
        required
        className="w-full px-4 bg-gray-800 py-2 rounded border focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      <div
        className="absolute right-3 top-2.5 cursor-pointer"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <InformationCircleIcon className="h-5 w-5 text-gray-500" />
        {showTooltip && (
          <div className="absolute right-2 top-[-16px] bg-gray-600 text-white text-xs rounded px-2 py-1 shadow-lg z-10 w-[200px]">
            This is a unique number provided by the NHS
          </div>
        )}
      </div>
    </div>

    {/* Password */}
    <div className="relative">
      <input
        type={showPassword ? "text" : "password"}
        name="password"
        placeholder="Password"
        value={formData.password}
        onChange={handleChange}
        required
        className="w-full px-4 py-2 bg-gray-800 rounded border focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      <span
        className="absolute right-3 top-2.5 cursor-pointer"
        onClick={() => setShowPassword((prev) => !prev)}
      >
        {showPassword ? (
          <EyeSlashIcon className="h-5 w-5 text-gray-500" />
        ) : (
          <EyeIcon className="h-5 w-5 text-gray-500" />
        )}
      </span>
    </div>

    {/* Submit Button */}
    <motion.button
      type="submit"
      disabled={isSubmitting}
      className={`w-full ${
        isSubmitting ? "bg-gray-400" : "bg-blue-600 hover:bg-blue-700"
      } text-white py-2 rounded transition-all duration-200 flex items-center justify-center`}
      whileTap={{ scale: 0.98 }}
      whileHover={{ scale: 1.03 }}
    >
      {isSubmitting ? (
        <div className="flex items-center space-x-2">
          <div className="h-4 w-4 rounded-full border-2 border-t-white animate-spin"></div>
        </div>
      ) : (
        <span>{isLogin ? "Log In" : "Register"}</span>
      )}
    </motion.button>
  </motion.form>
);
}

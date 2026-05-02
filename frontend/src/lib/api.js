import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const TOKEN_KEY = "calorie-scanner-token";

export const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const registerUser = async (payload) => (await api.post("/auth/register", payload)).data;

export const loginUser = async (payload) => (await api.post("/auth/login", payload)).data;

export const getCurrentUser = async () => (await api.get("/auth/me")).data;

export const getScanHistory = async () => (await api.get("/scans/history")).data;

export const getUserStreak = async () => (await api.get("/user/streak")).data;

export const analyzeFoodImage = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return (await api.post("/scans/analyze", formData, { headers: { "Content-Type": "multipart/form-data" } })).data;
};

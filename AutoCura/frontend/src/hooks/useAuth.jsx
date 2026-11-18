import { createContext, useContext, useMemo, useState } from "react";
import { AuthAPI } from "../services/endpoints";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("autocura_token"));

  const login = async (email, password) => {
    const response = await AuthAPI.login(email, password);
    localStorage.setItem("autocura_token", response.data.access_token);
    setToken(response.data.access_token);
  };

  const register = async (name, email, password) => {
    await AuthAPI.register(name, email, password);
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem("autocura_token");
    setToken(null);
  };

  const value = useMemo(
    () => ({ token, isAuthenticated: Boolean(token), login, register, logout }),
    [token]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

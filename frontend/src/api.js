import axios from "axios";

const API = axios.create({
  baseURL: "http://localhost:5000"
});

export const loginUser = (data) => API.post("/login", data);

export const getDevices = (token) =>
  API.get("/devices", {
    headers: { Authorization: `Bearer ${token}` }
  });

export const scanNetwork = (token) =>
  API.get("/scan", {
    headers: { Authorization: `Bearer ${token}` }
  });

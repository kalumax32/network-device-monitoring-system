import React, { useEffect, useState } from "react";
import { getDevices, scanNetwork } from "./api";
import { Bar } from "react-chartjs-2";
import "chart.js/auto";

function Dashboard({ token }) {
  const [devices, setDevices] = useState([]);

  const fetchDevices = async () => {
    const res = await getDevices(token);
    setDevices(res.data);
  };

  const handleScan = async () => {
    await scanNetwork(token);
    fetchDevices();
  };

  useEffect(() => {
    fetchDevices();
    const interval = setInterval(fetchDevices, 30000);
    return () => clearInterval(interval);
  }, []);

  const onlineCount = devices.filter(d=>d.status==="Online").length;
  const offlineCount = devices.length - onlineCount;

  const data = {
    labels: ["Online", "Offline"],
    datasets: [{ label: "Device Status", data: [onlineCount, offlineCount] }]
  };

  return (
    <div style={{ padding: "20px" }}>
      <h2>Network Monitoring Dashboard</h2>
      <button onClick={handleScan}>Scan Network</button>

      <table border="1" style={{ marginTop: "20px", width: "100%" }}>
        <thead>
          <tr>
            <th>IP</th>
            <th>Hostname</th>
            <th>Status</th>
            <th>Response Time</th>
            <th>Bandwidth In</th>
            <th>Bandwidth Out</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((d, i)=>(
            <tr key={i}>
              <td>{d.ip}</td>
              <td>{d.hostname}</td>
              <td>{d.status}</td>
              <td>{d.response_time}</td>
              <td>{d.bandwidth_in}</td>
              <td>{d.bandwidth_out}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ width: "400px", marginTop: "30px" }}>
        <Bar data={data} />
      </div>
    </div>
  );
}

export default Dashboard;

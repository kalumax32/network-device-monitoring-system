import React, { useEffect, useState } from "react";
import { getDevices, scanNetwork } from "./api";
import { Bar } from "react-chartjs-2";
import "chart.js/auto";
import { motion, AnimatePresence } from "framer-motion";
import { RefreshCw, Server, Wifi, WifiOff, Activity } from "lucide-react";

function Dashboard({ token }) {
  const [devices, setDevices] = useState([]);
  const [isScanning, setIsScanning] = useState(false);

  const fetchDevices = async () => {
    try {
      const res = await getDevices(token);
      setDevices(res.data);
    } catch (err) {
      console.error("Failed to fetch devices", err);
    }
  };

  const handleScan = async () => {
    setIsScanning(true);
    try {
      await scanNetwork(token);
      await fetchDevices();
    } finally {
      setIsScanning(false);
    }
  };

  useEffect(() => {
    fetchDevices();
    const interval = setInterval(fetchDevices, 30000);
    return () => clearInterval(interval);
  }, []);

  const onlineCount = devices.filter(d => d.status === "Online").length;
  const offlineCount = devices.length - onlineCount;

  // Sharp colors for the chart
  const chartData = {
    labels: ["Online", "Offline"],
    datasets: [{ 
      label: "Device Status", 
      data: [onlineCount, offlineCount],
      backgroundColor: ["#10B981", "#EF4444"], // Sharp Emerald Green and Red
      borderRadius: 6,
      borderWidth: 0,
    }]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false }
    },
    scales: {
      y: { grid: { color: "#334155" }, ticks: { color: "#94a3b8" } },
      x: { grid: { display: false }, ticks: { color: "#94a3b8" } }
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Activity className="text-cyan-400" /> Network Overview
          </h1>
          <p className="text-slate-400 mt-1">Real-time monitoring and analytics</p>
        </div>
        
        <button 
          onClick={handleScan} 
          disabled={isScanning}
          className="flex items-center gap-2 px-5 py-2.5 font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95 shadow-lg shadow-indigo-500/25"
        >
          <RefreshCw className={`w-5 h-5 ${isScanning ? "animate-spin" : ""}`} />
          {isScanning ? "Scanning..." : "Scan Network"}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatsCard title="Total Devices" value={devices.length} icon={<Server className="text-blue-400" />} />
        <StatsCard title="Online" value={onlineCount} icon={<Wifi className="text-emerald-400" />} />
        <StatsCard title="Offline" value={offlineCount} icon={<WifiOff className="text-red-400" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart Section */}
        <div className="lg:col-span-1 bg-slate-800 border border-slate-700 p-6 rounded-2xl shadow-xl">
          <h3 className="text-lg font-semibold mb-4">Status Distribution</h3>
          <div className="h-64">
            <Bar data={chartData} options={chartOptions} />
          </div>
        </div>

        {/* Data Table Section */}
        <div className="lg:col-span-2 bg-slate-800 border border-slate-700 p-6 rounded-2xl shadow-xl overflow-hidden">
          <h3 className="text-lg font-semibold mb-4">Device Directory</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-sm uppercase tracking-wider">
                  <th className="py-3 px-4">IP Address</th>
                  <th className="py-3 px-4">Hostname</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Response Time</th>
                  <th className="py-3 px-4">Bandwidth (In/Out)</th>
                </tr>
              </thead>
              <tbody>
                <AnimatePresence>
                  {devices.map((d, i) => (
                    <motion.tr 
                      key={d.ip || i}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors"
                    >
                      <td className="py-4 px-4 font-mono text-sm text-cyan-300">{d.ip}</td>
                      <td className="py-4 px-4 font-medium">{d.hostname || "Unknown"}</td>
                      <td className="py-4 px-4">
                        <span className={`px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1.5 w-max ${
                          d.status === "Online" 
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                            : "bg-red-500/10 text-red-400 border border-red-500/20"
                        }`}>
                          <span className={`w-2 h-2 rounded-full ${d.status === "Online" ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`}></span>
                          {d.status}
                        </span>
                      </td>
                      <td className="py-4 px-4 text-slate-300">{d.response_time || "-"}</td>
                      <td className="py-4 px-4 text-slate-300">
                        {d.bandwidth_in} / {d.bandwidth_out}
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

// Reusable micro-component for the top stats
function StatsCard({ title, value, icon }) {
  return (
    <motion.div 
      whileHover={{ y: -5 }}
      className="bg-slate-800 border border-slate-700 p-6 rounded-2xl shadow-xl flex items-center justify-between"
    >
      <div>
        <p className="text-slate-400 text-sm font-medium">{title}</p>
        <p className="text-3xl font-bold mt-2">{value}</p>
      </div>
      <div className="p-4 bg-slate-900 rounded-xl shadow-inner">
        {icon}
      </div>
    </motion.div>
  );
}

export default Dashboard;
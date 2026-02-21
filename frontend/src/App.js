import React, { useState } from "react";
import Login from "./Login";
import Dashboard from "./Dashboard";

function App() {
  const [token, setToken] = useState(null);
  
  return (
    <div className="min-h-screen bg-slate-900 ...">
      {token ? <Dashboard token={token} /> : <Login setToken={setToken} />}
    </div>
  );
}

export default App;
import { useEffect, useState } from "react";

function App() {
  const [status, setStatus] = useState("loading...");

  useEffect(() => {
    fetch("http://localhost:8000/health")
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch((error) => setStatus(`error: ${String(error)}`));
  }, []);

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>Backend Health</h1>
      <p>status = {status}</p>
    </main>
  );
}

export default App;

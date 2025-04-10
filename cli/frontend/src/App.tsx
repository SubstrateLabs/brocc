import StatusComponent from "./components/status";

function App() {
  return (
    <div className="flex flex-col min-h-screen">
      <StatusComponent />
      <div className="p-2 flex-1">{/* Main content goes here */}</div>
    </div>
  );
}

export default App;

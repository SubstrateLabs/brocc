import ChromeStatusComponent from './components/chrome-status'

function App() {
  return (
    <div className="flex flex-col min-h-screen">
      <ChromeStatusComponent />
      <div className="p-2 flex-1">
        {/* Main content goes here */}
      </div>
    </div>
  );
}

export default App

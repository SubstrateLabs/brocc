import { useState, useEffect, ReactNode } from 'react';
import { Button } from "@/components/ui/button"
import { SquareArrowOutUpRight, Info, TriangleAlert, ArrowRight } from 'lucide-react';

// API endpoints
const API_URL = 'http://127.0.0.1:8022';
const CHROME_STATUS_URL = `${API_URL}/chrome/status`;
const CHROME_LAUNCH_URL = `${API_URL}/chrome/launch`;
const CHROME_STARTUP_FAQ_URL = `${API_URL}/chrome/startup-faq`;

// Chrome status codes - keep in sync with backend ChromeStatus enum
const CHROME_STATUS = {
  CONNECTED: "connected",
  NOT_RUNNING: "not_running",
  RUNNING_WITHOUT_DEBUG_PORT: "running_without_debug_port",
  CONNECTING: "connecting",
};

interface ChromeStatus {
  status_code: string;
  timestamp: number;
}

// Reusable container component
type StatusContainerProps = {
  children: ReactNode;
};

const StatusContainer = ({ children }: StatusContainerProps) => {
  return (
    <div className="w-full sticky top-0 px-2 py-1 border border-dotted border-muted-foreground bg-background z-10">
       {children}
    </div>
  );
};

// Reusable simple status message component
const StatusMessage = ({ message, showSpinner = false }: { message: string, showSpinner?: boolean }) => (
  <div className="flex items-center justify-center">
    {showSpinner && (
      <div className="mr-2 h-4 w-4 rounded-full border-2 border-t-transparent border-current animate-spin" />
    )}
    <p className="text-xs">{message}</p>
  </div>
);

type ApiOptions = {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
};

export default function ChromeStatusComponent() {
  const [status, setStatus] = useState<ChromeStatus | null>(null);
  const [isLaunching, setIsLaunching] = useState(false);

  // Helper function for API error handling
  const apiCall = async (url: string, options: ApiOptions = {}) => {
    try {
      const response = await fetch(url, options);
      if (response.ok && options.method !== 'POST') {
        return await response.json();
      }
      return true;
    } catch (error) {
      console.error(`Error with API call to ${url}:`, error);
      return false;
    }
  };

  // Function to fetch status
  const fetchStatus = async () => {
    const data = await apiCall(CHROME_STATUS_URL);
    if (data) {
      setStatus(data);
      
      // Clear launching state if connected
      if (data.status_code === CHROME_STATUS.CONNECTED) {
        setIsLaunching(false);
      }
    }
  };

  // Launch Chrome
  const launchChrome = async (forceRelaunch = false) => {
    setIsLaunching(true);
    
    await apiCall(CHROME_LAUNCH_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ force_relaunch: forceRelaunch }),
    });
  };

  // Open FAQ
  const openFaq = () => apiCall(CHROME_STARTUP_FAQ_URL, { method: 'POST' });

  // Fetch status initially and poll frequently (500ms)
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 500);
    return () => clearInterval(interval);
  }, []);

  // Determine which UI state to render
  const renderContent = () => {
    // Launching state
    if (isLaunching) {
      return (
        <StatusContainer>
          <StatusMessage message="Launching Chrome and connecting..." showSpinner={true} />
        </StatusContainer>
      );
    }

    // Loading state
    if (!status) {
      return (
        <StatusContainer>
          <StatusMessage message="Checking Chrome status..." showSpinner={false} />
        </StatusContainer>
      );
    }

    // Connected state
    if (status.status_code === CHROME_STATUS.CONNECTED) {
      return (
        <StatusContainer>
          <StatusMessage message="Connected to Chrome" />
        </StatusContainer>
      );
    }

    // Not running - need to launch Chrome
    if (status.status_code === CHROME_STATUS.NOT_RUNNING) {
      return (
        <StatusContainer>
          <div className="flex items-center justify-between w-full">
            <p className="flex items-center">
              Not connected. Please launch Chrome to begin syncing
              <ArrowRight className="ml-2 h-4 w-4" />
            </p>
            <Button onClick={() => launchChrome(false)}>
              <SquareArrowOutUpRight className="mr-2 h-4 w-4" />
              Launch Chrome
            </Button>
          </div>
        </StatusContainer>
      );
    }

    // Running without debug port - need to relaunch
    if (status.status_code === CHROME_STATUS.RUNNING_WITHOUT_DEBUG_PORT) {
      return (
        <StatusContainer>
          <div className="flex items-center justify-between w-full">
            <p className="flex items-center">
              Not connected. Please relaunch Chrome to begin syncing
              <ArrowRight className="ml-2 h-4 w-4" />
            </p>
            <Button onClick={() => launchChrome(true)}>
              <SquareArrowOutUpRight className="mr-2 h-4 w-4" />
              Relaunch Chrome
            </Button>
          </div>
          <div className="flex items-center justify-between w-full mt-2">
            <p className="text-muted-foreground flex items-center">
              <TriangleAlert className="mr-2 h-4 w-4 text-amber-500" />
              You may lose your open tabs when Brocc relaunches Chrome. 
              To prevent this, check your startup settings:
            </p>
            <Button 
              onClick={openFaq}
              size="sm"
              variant="outline"
            >
              <Info className="mr-2 h-4 w-4" />
              Chrome startup
            </Button>
          </div>
        </StatusContainer>
      );
    }

    // Default: connecting state
    return (
      <StatusContainer>
        <StatusMessage message="Connecting to Chrome..." showSpinner={true} />
      </StatusContainer>
    );
  };

  return renderContent();
}

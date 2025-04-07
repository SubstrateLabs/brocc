import { useState, useEffect, ReactNode } from 'react';
import { Button } from "@/components/ui/button"
import { SiGooglechrome } from '@icons-pack/react-simple-icons';
import { SquareArrowOutUpRight, Info } from 'lucide-react';

// API endpoints
const API_URL = 'http://127.0.0.1:8022';
const CHROME_STATUS_URL = `${API_URL}/chrome/status`;
const CHROME_LAUNCH_URL = `${API_URL}/chrome/launch`;
const CHROME_STARTUP_FAQ_URL = `${API_URL}/chrome/startup-faq`;

interface ChromeStatus {
  status: string;
  is_connected: boolean;
  requires_relaunch: boolean;
  timestamp: number;
}

// Reusable container component
type StatusContainerProps = {
  children: ReactNode;
};

const StatusContainer = ({ children }: StatusContainerProps) => {
  return (
    <div className="max-w-md mx-auto p-1 border border-dotted border-muted-foreground rounded relative">
      <div className="absolute -bottom-3 -right-3 p-1">
        <SiGooglechrome className="h-5 w-5" />
      </div>
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
    <p>{message}</p>
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
      if (data.is_connected) {
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
    if (status.is_connected) {
      return (
        <StatusContainer>
          <StatusMessage message="Connected to Chrome" />
        </StatusContainer>
      );
    }

    // Need to launch Chrome
    const isRunning = !status.status.includes('not running');
    const needsRelaunch = status.requires_relaunch;

    if (!isRunning) {
      return (
        <StatusContainer>
          <p className="mb-2">Not connected. Brocc needs to launch Chrome to sync your browsing activity.</p>
          <Button onClick={() => launchChrome(false)}>
            <SquareArrowOutUpRight className="mr-2 h-4 w-4" />
            Launch Chrome
          </Button>
        </StatusContainer>
      );
    }

    if (needsRelaunch) {
      return (
        <StatusContainer>
          <p className="mb-2">Not connected. Brocc needs to relaunch Chrome to sync your browsing activity.</p>
          <Button onClick={() => launchChrome(true)}>
            <SquareArrowOutUpRight className="mr-2 h-4 w-4" />
            Relaunch Chrome
          </Button>
          <div className="mt-2 text-sm">
            <p className="text-muted-foreground">
              Note: you may lose your open tabs when Brocc relaunches Chrome. 
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

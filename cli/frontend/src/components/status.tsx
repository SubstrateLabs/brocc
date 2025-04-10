import { useState, useEffect, ReactNode, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import {
  SquareArrowOutUpRight,
  Info,
  TriangleAlert,
  ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

// API endpoints
const API_URL = "http://127.0.0.1:8022";
const CHROME_STATUS_URL = `${API_URL}/chrome/status`;
const CHROME_LAUNCH_URL = `${API_URL}/chrome/launch`;
const CHROME_STARTUP_FAQ_URL = `${API_URL}/chrome/startup-faq`;
const AUTH_STATUS_URL = `${API_URL}/auth/status`;
const OPEN_DASHBOARD_URL = `${API_URL}/auth/open-dashboard`;
const LOGIN_START_URL = `${API_URL}/auth/login/start`;
const LOGIN_POLL_URL = `${API_URL}/auth/login/poll`;

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

interface AuthStatus {
  is_logged_in: boolean;
  email?: string | null;
}

// Reusable container component
type StatusContainerProps = {
  children: ReactNode;
  isConnected?: boolean;
};

const StatusContainer = ({
  children,
  isConnected = false,
}: StatusContainerProps) => {
  return (
    <div
      className={cn(
        "w-full sticky top-0 px-2 py-1 bg-background z-10",
        !isConnected && "border border-dotted border-muted-foreground",
      )}
    >
      {children}
    </div>
  );
};

// Reusable simple status message component
const StatusMessage = ({
  message,
  showSpinner = false,
  isConnected = false,
  isLoggingIn = false,
  loginError = null,
}: {
  message: string;
  showSpinner?: boolean;
  isConnected?: boolean;
  isLoggingIn?: boolean;
  loginError?: string | null;
}) => (
  <div
    className={cn(
      "flex items-center",
      !isConnected && "justify-center",
      isConnected && "justify-start",
    )}
  >
    {isConnected && <div className="mr-2 h-2 w-2 rounded-full bg-green-500" />}
    {showSpinner && (
      <div className="mr-2 h-4 w-4 rounded-full border-2 border-t-transparent border-current animate-spin" />
    )}
    <p className="text-xs">{message}</p>
    {isLoggingIn && (
      <div className="ml-2 h-4 w-4 rounded-full border-2 border-t-transparent border-blue-500 animate-spin" />
    )}
    {loginError && (
      <p className="ml-2 text-xs text-red-500">Error: {loginError}</p>
    )}
  </div>
);

type ApiOptions = {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
};

export default function StatusComponent() {
  const [status, setStatus] = useState<ChromeStatus | null>(null);
  const [isLaunching, setIsLaunching] = useState(false);
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const loginPollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Helper function for API error handling - wrapped in useCallback
  const apiCall = useCallback(async (url: string, options: ApiOptions = {}) => {
    try {
      const response = await fetch(url, options);
      if (response.ok && options.method !== "POST") {
        return await response.json();
      }
      // Handle non-json POST responses or failed responses
      if (response.ok) return true; // Successful POST
      // Log error for non-ok responses before returning false
      console.error(`API call to ${url} failed with status ${response.status}`);
      return false;
    } catch (error) {
      console.error(`Error with API call to ${url}:`, error);
      return false;
    }
  }, []); // Empty dependency array as it only uses constants

  // Function to fetch status - wrapped in useCallback
  const fetchStatus = useCallback(async () => {
    // Fetch only Chrome status
    const chromeData = await apiCall(CHROME_STATUS_URL);

    if (chromeData) {
      setStatus(chromeData);

      // Clear launching state if connected
      if (chromeData.status_code === CHROME_STATUS.CONNECTED) {
        setIsLaunching(false);
      }
    }
    // Removed the conditional fetch of initial auth status
  }, [apiCall]); // Dependencies: apiCall (state setters are stable)

  // Function to open dashboard
  const openDashboard = useCallback(
    () => apiCall(OPEN_DASHBOARD_URL, { method: "POST" }),
    [apiCall],
  );

  // Launch Chrome
  const launchChrome = useCallback(
    async (forceRelaunch = false) => {
      setIsLaunching(true);

      await apiCall(CHROME_LAUNCH_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ force_relaunch: forceRelaunch }),
      });
    },
    [apiCall],
  ); // Dependencies: apiCall (setIsLaunching is stable)

  // Open FAQ
  const openFaq = useCallback(
    () => apiCall(CHROME_STARTUP_FAQ_URL, { method: "POST" }),
    [apiCall],
  );

  // --- Login Flow Functions ---

  // Function to clear the interval and reset the ref
  const clearLoginPollInterval = useCallback(() => {
    if (loginPollIntervalRef.current) {
      clearInterval(loginPollIntervalRef.current);
      loginPollIntervalRef.current = null;
    }
  }, []); // No dependencies needed

  // Moved pollLoginStatus definition before startLoginFlow
  const pollLoginStatus = useCallback(
    async (sessionId: string | null) => {
      if (!sessionId) return;

      const pollUrl = `${LOGIN_POLL_URL}?session_id=${sessionId}`;
      const data = await apiCall(pollUrl, { method: "GET" });

      if (data) {
        if (data.status === "complete") {
          setIsLoggingIn(false);
          setLoginError(null);
          clearLoginPollInterval(); // Use the ref-based clear function
          setAuthStatus({ is_logged_in: true, email: data.email });
          fetchStatus(); // Refresh overall status
          apiCall(`${API_URL}/webview/focus`, { method: "POST" });
        } else if (data.status === "error") {
          setLoginError(data.message || "Polling failed.");
          setIsLoggingIn(false);
          clearLoginPollInterval(); // Use the ref-based clear function
        } else {
          // console.log("Login poll status:", data.status); // 'pending'
        }
      } else {
        console.error("Login poll API call failed");
        setLoginError("Network error during login poll.");
        setIsLoggingIn(false);
        clearLoginPollInterval(); // Use the ref-based clear function
      }
    },
    // Removed loginPollIntervalId from dependencies
    [apiCall, fetchStatus, clearLoginPollInterval],
  );

  const startLoginFlow = useCallback(async () => {
    setIsLoggingIn(true);
    setLoginError(null);
    clearLoginPollInterval(); // Clear any existing interval first

    const data = await apiCall(LOGIN_START_URL, { method: "GET" });
    if (data && data.auth_url && data.session_id) {
      // Start polling with the received session ID
      // Store interval ID in ref
      loginPollIntervalRef.current = setInterval(
        () => pollLoginStatus(data.session_id),
        1000,
      );
    } else {
      setLoginError("Failed to initiate login.");
      setIsLoggingIn(false);
    }
  }, [apiCall, clearLoginPollInterval, pollLoginStatus]); // Added pollLoginStatus dependency

  // Fetch status initially and poll frequently (500ms)
  useEffect(() => {
    // Fetch initial Chrome status
    fetchStatus();

    // Fetch initial Auth status ONCE
    const fetchInitialAuth = async () => {
      const initialAuthData = await apiCall(AUTH_STATUS_URL);
      if (initialAuthData) {
        setAuthStatus(initialAuthData);
      }
    };
    fetchInitialAuth();

    // Set up interval for Chrome status polling
    const interval = setInterval(fetchStatus, 500);
    return () => clearInterval(interval);
  }, [fetchStatus, apiCall]); // <-- Added apiCall dependency for fetchInitialAuth

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      clearLoginPollInterval();
    };
  }, [clearLoginPollInterval]);

  // Determine which UI state to render
  const renderContent = () => {
    // --- Authentication Check First ---

    // 1. Loading Auth Status
    if (authStatus === null) {
      return (
        <StatusContainer>
          <StatusMessage message="..." showSpinner={false} />
        </StatusContainer>
      );
    }

    // 2. Not Logged In
    if (!authStatus.is_logged_in) {
      return (
        <StatusContainer isConnected={false}>
          <div className="flex items-center justify-between w-full">
            <p className="text-xs mr-2">Please log in to get started.</p>
            <Button
              size="sm"
              variant="outline"
              onClick={startLoginFlow}
              disabled={isLoggingIn}
            >
              {isLoggingIn ? "Logging in..." : "Login"}
              {isLoggingIn && (
                <div className="ml-2 h-4 w-4 rounded-full border-2 border-t-transparent border-current animate-spin" />
              )}
            </Button>
          </div>
          {loginError && (
            <div className="flex justify-center w-full mt-1">
              <p className="text-xs text-red-500">Error: {loginError}</p>
            </div>
          )}
        </StatusContainer>
      );
    }

    // --- Chrome Status Check (Only if Logged In) ---

    // 3. Launching Chrome
    if (isLaunching) {
      return (
        <StatusContainer isConnected={true}>
          {" "}
          {/* Assume connection intent */}
          <StatusMessage
            message="Launching Chrome and connecting..."
            showSpinner={true}
            isConnected={true}
          />
        </StatusContainer>
      );
    }

    // 4. Loading Chrome Status
    if (!status) {
      return (
        <StatusContainer isConnected={true}>
          {" "}
          {/* Assume connection intent */}
          <StatusMessage
            message="Checking Chrome status..."
            showSpinner={false}
            isConnected={true}
          />
        </StatusContainer>
      );
    }

    // 5. Chrome Connected (and Logged In)
    if (status.status_code === CHROME_STATUS.CONNECTED) {
      return (
        <StatusContainer isConnected={true}>
          <div className="flex items-center justify-start">
            {<div className="mr-2 h-2 w-2 rounded-full bg-green-500" />}
            {/* Simplified: We already know they are logged in */}
            <p className="text-xs mr-1">Connected |</p>
            <Button
              variant="link"
              className="text-xs p-0 h-auto text-foreground font-normal"
              onClick={openDashboard}
            >
              Logged in as {authStatus.email}
            </Button>
          </div>
        </StatusContainer>
      );
    }

    // 6. Chrome Not Running (and Logged In)
    if (status.status_code === CHROME_STATUS.NOT_RUNNING) {
      return (
        <StatusContainer isConnected={true}>
          {" "}
          {/* Still logged in */}
          <div className="flex items-center justify-between w-full">
            <p className="flex items-center text-xs">
              Logged in | Chrome not running. Please launch Chrome to sync.
              <ArrowRight className="ml-2 h-4 w-4" />
            </p>
            <Button size="sm" onClick={() => launchChrome(false)}>
              <SquareArrowOutUpRight className="mr-2 h-4 w-4" />
              Launch Chrome
            </Button>
          </div>
        </StatusContainer>
      );
    }

    // 7. Chrome Running without Debug Port (and Logged In)
    if (status.status_code === CHROME_STATUS.RUNNING_WITHOUT_DEBUG_PORT) {
      return (
        <StatusContainer isConnected={true}>
          {" "}
          {/* Still logged in */}
          <div className="flex items-center justify-between w-full">
            <p className="flex items-center text-xs">
              Logged in | Chrome needs relaunch to sync.
              <ArrowRight className="ml-2 h-4 w-4" />
            </p>
            <Button size="sm" onClick={() => launchChrome(true)}>
              <SquareArrowOutUpRight className="mr-2 h-4 w-4" />
              Relaunch Chrome
            </Button>
          </div>
          <div className="flex items-center justify-between w-full mt-2">
            <p className="text-muted-foreground flex items-center text-xs">
              <TriangleAlert className="mr-2 h-4 w-4 text-amber-500" />
              Relaunching may close tabs. Check startup settings:
            </p>
            <Button onClick={openFaq} size="sm" variant="outline">
              <Info className="mr-2 h-4 w-4" />
              Chrome startup
            </Button>
          </div>
        </StatusContainer>
      );
    }

    // 8. Default: Connecting to Chrome (and Logged In)
    return (
      <StatusContainer isConnected={true}>
        {" "}
        {/* Still logged in */}
        <StatusMessage
          message={`Logged in as ${authStatus.email} | Connecting to Chrome...`}
          showSpinner={true}
          isConnected={true}
        />
      </StatusContainer>
    );
  };

  return renderContent();
}

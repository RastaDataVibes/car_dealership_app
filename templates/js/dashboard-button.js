// dashboard-button.js

// Dashboard overlay and buttons
const dashboardBtn = document.getElementById('dashboardBtn');
const dashboardOverlay = document.getElementById('dashboardContainer');
const dashboardClose = document.getElementById('closeDashboardBtn');

// Superset embed settings
const DASHBOARD_ID = 'e9413e09-3526-47c6-9867-e9230f411f3b'; // your dashboard ID
const SUPERSET_URL = 'http://localhost:8088'; // your Superset URL

// Track if dashboard is already loaded
let isDashboardLoaded = false;

function renderDashboard() {
  // Only embed once
  if (isDashboardLoaded) return;

  // Clear previous content except close button
  dashboardOverlay.innerHTML = '';
  dashboardOverlay.appendChild(dashboardClose);

  // Embed dashboard using Superset SDK
  superset.embedDashboard({
    id: DASHBOARD_ID,
    mountPoint: dashboardOverlay,
    supersetDomain: SUPERSET_URL,
    fetchToken: () => Promise.resolve(null), // no token needed for public dashboards
  });

  isDashboardLoaded = true;
}

// Open dashboard on button click
dashboardBtn.addEventListener('click', () => {
  dashboardOverlay.style.display = 'block';
  renderDashboard();
});

// Close dashboard
dashboardClose.addEventListener('click', () => {
  dashboardOverlay.style.display = 'none';
});


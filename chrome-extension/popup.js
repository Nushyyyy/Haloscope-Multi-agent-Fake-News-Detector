// Configuration
const API_URL = 'http://127.0.0.1:5000/analyze';

// DOM Elements
const analyzeBtn = document.getElementById('analyzeBtn');
const loading = document.getElementById('loading');
const results = document.getElementById('results');
const errorDiv = document.getElementById('error');
const errorMsg = document.getElementById('errorMsg');

// Analyze button click handler
analyzeBtn.addEventListener('click', async () => {
  try {
    // Get current tab URL
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (!tab.url) {
      showError('Cannot analyze this page');
      return;
    }
    
    // Show loading state
    showLoading();
    
    // Call backend API
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: tab.url })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    
    if (data.error) {
      throw new Error(data.error);
    }
    
    // Display results
    displayResults(data);
    
  } catch (error) {
    console.error('Analysis error:', error);
    showError(error.message || 'Failed to analyze page. Make sure the backend is running on port 5000.');
  }
});

function showLoading() {
  analyzeBtn.disabled = true;
  loading.style.display = 'block';
  results.style.display = 'none';
  errorDiv.style.display = 'none';
}

function hideLoading() {
  analyzeBtn.disabled = false;
  loading.style.display = 'none';
}

function showError(message) {
  hideLoading();
  errorMsg.textContent = message;
  errorDiv.style.display = 'block';
  results.style.display = 'none';
}

function displayResults(data) {
  hideLoading();
  
  // Trust Score
  const trustScore = data.source_score || 0;
  const trustPercent = Math.round(trustScore * 100);
  document.getElementById('trustScore').textContent = `${trustPercent}%`;
  
  const trustBar = document.getElementById('trustBar');
  trustBar.style.width = `${trustPercent}%`;
  
  if (trustScore >= 0.8) {
    trustBar.className = 'score-fill';
  } else if (trustScore >= 0.6) {
    trustBar.className = 'score-fill medium';
  } else {
    trustBar.className = 'score-fill low';
  }
  
  // Domain
  document.getElementById('domain').textContent = data.domain || 'Unknown';
  
  // Credibility
  const credScore = data.credibility?.credibility_score || 0;
  const credPercent = Math.round(credScore * 100);
  document.getElementById('credibility').textContent = `${credPercent}% - ${data.credibility?.factual_reporting || 'Unknown'}`;
  
  const credibilityBadge = document.getElementById('credibilityBadge');
  let badgeClass = 'low';
  let badgeText = 'Low Trust';
  
  if (credScore >= 0.8) {
    badgeClass = 'high';
    badgeText = 'High Trust';
  } else if (credScore >= 0.6) {
    badgeClass = 'medium';
    badgeText = 'Medium Trust';
  }
  
  credibilityBadge.innerHTML = `<span class="badge ${badgeClass}">${badgeText}</span>`;
  
  // Language
  const lang = data.language?.language || 'Unknown';
  const langConf = data.language?.confidence || 0;
  document.getElementById('language').textContent = `${lang} (${langConf}% confidence)`;
  
  // Claims
  const claims = data.claims || [];
  document.getElementById('claimsCount').textContent = claims.length;
  
  const claimsList = document.getElementById('claimsList');
  claimsList.innerHTML = '';
  
  if (claims.length > 0) {
    claims.slice(0, 3).forEach((claim, index) => {
      const claimDiv = document.createElement('div');
      claimDiv.className = 'claim';
      const preview = claim.length > 100 ? claim.substring(0, 100) + '...' : claim;
      claimDiv.textContent = `${index + 1}. ${preview}`;
      claimsList.appendChild(claimDiv);
    });
  }
  
  // Show results
  results.style.display = 'block';
  errorDiv.style.display = 'none';
}

// Check backend on load
window.addEventListener('load', async () => {
  try {
    const response = await fetch('http://127.0.0.1:5000/health', {
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    });
    
    if (!response.ok) {
      console.warn('Backend not responding properly');
    }
  } catch (error) {
    console.warn('Backend not accessible:', error.message);
    // Don't show error yet, wait until user clicks analyze
  }
});
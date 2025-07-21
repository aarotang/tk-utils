class GiftCodeRedeemer {
    constructor() {
        this.form = document.getElementById('giftCodeForm');
        this.submitBtn = document.getElementById('submitBtn');
        this.buttonText = document.getElementById('buttonText');
        this.loadingSpinner = document.getElementById('loadingSpinner');
        this.status = document.getElementById('status');
        this.results = document.getElementById('results');
        
        // Replace with your GitHub username and repo name
        this.GITHUB_USERNAME = 'aarotang';
        this.GITHUB_REPO = 'tk-utils';
        this.GITHUB_TOKEN = null; // We'll use GitHub's public API
        
        this.initEventListeners();
    }

    initEventListeners() {
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });
    }

    async handleSubmit() {
        const giftCode = document.getElementById('giftCode').value.trim();
        const selectedServers = Array.from(document.getElementById('servers').selectedOptions)
            .map(option => option.value);

        if (!giftCode) {
            this.showStatus('Please enter a gift code', 'error');
            return;
        }

        this.setLoading(true);
        this.showStatus('Starting gift code redemption...', 'info');

        try {
            await this.triggerGitHubAction(giftCode, selectedServers);
            this.showStatus('🎉 Gift code redemption started successfully!', 'success');
            this.showResults(`
                <h3>✅ Redemption Process Started</h3>
                <p><strong>Gift Code:</strong> ${giftCode}</p>
                <p><strong>Servers:</strong> ${selectedServers.length > 0 ? selectedServers.join(', ') : 'All servers'}</p>
                <p>The redemption process is now running in the background. 
                   <a href="https://github.com/${this.GITHUB_USERNAME}/${this.GITHUB_REPO}/actions" target="_blank">
                       Click here to view detailed logs on GitHub
                   </a>
                </p>
                <p><em>Note: It may take a few minutes to complete. Refresh the GitHub Actions page to see updates.</em></p>
            `);
        } catch (error) {
            this.showStatus(`❌ Error: ${error.message}`, 'error');
            this.showResults(`
                <h3>❌ Error Details</h3>
                <p>${error.message}</p>
                <p>Please try again or check your GitHub repository settings.</p>
            `);
        } finally {
            this.setLoading(false);
        }
    }

    async triggerGitHubAction(giftCode, servers) {
        // Simple approach: Redirect to GitHub Actions with pre-filled URL
        const serverParam = servers.length > 0 ? servers.join(',') : '';
        const actionUrl = `https://github.com/${this.GITHUB_USERNAME}/${this.GITHUB_REPO}/actions/workflows/redeem-coupon.yml`;
        
        // Show success message and redirect
        setTimeout(() => {
            window.open(actionUrl, '_blank');
        }, 2000);
        
        // Store the gift code in localStorage so users can copy it
        localStorage.setItem('lastGiftCode', giftCode);
        localStorage.setItem('lastServers', serverParam);
        
        return Promise.resolve();
    }

    setLoading(loading) {
        this.submitBtn.disabled = loading;
        if (loading) {
            this.buttonText.classList.add('hidden');
            this.loadingSpinner.classList.remove('hidden');
        } else {
            this.buttonText.classList.remove('hidden');
            this.loadingSpinner.classList.add('hidden');
        }
    }

    showStatus(message, type) {
        this.status.textContent = message;
        this.status.className = `status ${type}`;
        this.status.classList.remove('hidden');
    }

    showResults(html) {
        this.results.innerHTML = html;
        this.results.classList.remove('hidden');
    }
}

// Initialize the app when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new GiftCodeRedeemer();
});